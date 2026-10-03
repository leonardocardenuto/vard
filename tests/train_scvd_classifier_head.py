from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import cv2
import matplotlib
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset, TensorDataset
from transformers import AutoModel, AutoVideoProcessor

matplotlib.use("Agg")
import matplotlib.pyplot as plt


MODEL_NAME = "facebook/vjepa2-vitl-fpc64-256"
CLASS_NAMES = ["Normal", "Violence", "Weaponized"]
CLASS_TO_ID = {name: index for index, name in enumerate(CLASS_NAMES)}
VIDEO_SUFFIXES = {".avi", ".mp4", ".mov", ".mkv", ".webm"}
DEFAULT_SEED = 42
PROJECT_ROOT = Path(__file__).resolve().parents[1]
HF_CACHE_DIR = PROJECT_ROOT / ".cache" / "huggingface"
HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(HF_CACHE_DIR))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_CACHE_DIR))


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


@dataclass(frozen=True)
class VideoSample:
    video_path: str
    label: int
    split: str
    sample_id: str
    source_id: str
    start_frame: int | None = None
    end_frame: int | None = None


@dataclass
class EpochMetrics:
    epoch: int
    train_loss: float
    train_accuracy: float
    train_f1_macro: float
    val_loss: float
    val_accuracy: float
    val_f1_macro: float
    val_f1_weighted: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Treina somente uma nova cabeca classificadora V-JEPA 2 no SCVD."
    )
    parser.add_argument("--dataset-root", default=r"D:\archive\SCVD")
    parser.add_argument(
        "--dataset-variant",
        choices=("SCVD_converted_sec_split", "SCVD_converted"),
        default="SCVD_converted",
    )
    parser.add_argument("--output-dir", default="var/training_runs/scvd_head")
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument(
        "--clip-duration-seconds",
        type=float,
        default=0.0,
        help="Divide cada video original em janelas temporais; use 0 para o video inteiro.",
    )
    parser.add_argument("--min-tail-fraction", type=float, default=0.5)
    parser.add_argument("--feature-batch-size", type=int, default=2)
    parser.add_argument("--feature-workers", type=int, default=0)
    parser.add_argument("--head-batch-size", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=5e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.35)
    parser.add_argument("--hidden-dim", type=int, default=512)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-frame-side", type=int, default=960)
    parser.add_argument("--log-every", type=int, default=100)
    parser.add_argument(
        "--max-samples-per-class",
        type=int,
        default=0,
        help="Limite por classe em cada split; use apenas para smoke tests.",
    )
    parser.add_argument(
        "--reuse-feature-cache",
        action="store_true",
        help="Reutiliza embeddings existentes quando metadados e parametros coincidirem.",
    )
    parser.add_argument(
        "--allow-cross-split-duplicates",
        action="store_true",
        help="Permite duplicatas exatas entre Train/Test (nao recomendado; invalida a avaliacao).",
    )
    parser.add_argument("--disable-amp", action="store_true")
    parser.add_argument(
        "--skip-refit-on-all-train",
        action="store_true",
        help="Nao reajusta a cabeca final em Train+Validation apos selecionar a melhor epoca.",
    )
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def resolve_variant_root(dataset_root: Path, variant: str) -> Path:
    direct = dataset_root / variant
    if direct.exists():
        return direct
    if dataset_root.name == variant and dataset_root.exists():
        return dataset_root
    raise FileNotFoundError(f"Versao do SCVD nao encontrada: {direct}")


def collect_split_samples(variant_root: Path, split: str) -> list[VideoSample]:
    samples: list[VideoSample] = []
    split_root = variant_root / split
    if not split_root.exists():
        raise FileNotFoundError(f"Split nao encontrado: {split_root}")

    for class_name in CLASS_NAMES:
        class_root = split_root / class_name
        if not class_root.exists():
            raise FileNotFoundError(f"Classe nao encontrada: {class_root}")
        for video_path in sorted(class_root.rglob("*")):
            if video_path.suffix.lower() not in VIDEO_SUFFIXES:
                continue
            samples.append(
                VideoSample(
                    video_path=str(video_path),
                    label=CLASS_TO_ID[class_name],
                    split=split.lower(),
                    sample_id=video_path.stem,
                    source_id=f"{split.lower()}:{class_name}:{video_path.stem}",
                )
            )

    if not samples:
        raise RuntimeError(f"Nenhum video encontrado em {split_root}")
    return samples


def limit_per_class(samples: Sequence[VideoSample], maximum: int, seed: int) -> list[VideoSample]:
    if maximum <= 0:
        return list(samples)
    rng = random.Random(seed)
    limited: list[VideoSample] = []
    for label in range(len(CLASS_NAMES)):
        class_samples = [sample for sample in samples if sample.label == label]
        rng.shuffle(class_samples)
        limited.extend(class_samples[:maximum])
    rng.shuffle(limited)
    return limited


def summarize(samples: Sequence[VideoSample]) -> dict[str, int]:
    counts = Counter(sample.label for sample in samples)
    return {name: int(counts[index]) for index, name in enumerate(CLASS_NAMES)}


def expand_videos_to_clips(
    samples: Sequence[VideoSample], clip_duration_seconds: float, min_tail_fraction: float
) -> list[VideoSample]:
    if clip_duration_seconds <= 0:
        return list(samples)
    clips: list[VideoSample] = []
    for sample in samples:
        cap = cv2.VideoCapture(sample.video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Nao foi possivel abrir o video: {sample.video_path}")
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        cap.release()
        if total_frames <= 0 or fps <= 0:
            raise RuntimeError(f"Metadados de video invalidos: {sample.video_path}")
        window_frames = max(1, int(round(fps * clip_duration_seconds)))
        clip_index = 0
        for start_frame in range(0, total_frames, window_frames):
            remaining = total_frames - start_frame
            if start_frame > 0 and remaining < window_frames * min_tail_fraction:
                break
            end_frame = min(total_frames - 1, start_frame + window_frames - 1)
            clips.append(
                VideoSample(
                    video_path=sample.video_path,
                    label=sample.label,
                    split=sample.split,
                    sample_id=f"{sample.sample_id}:clip{clip_index:03d}",
                    source_id=sample.source_id,
                    start_frame=start_frame,
                    end_frame=end_frame,
                )
            )
            clip_index += 1
    log(f"Segmentacao temporal: {len(samples)} videos -> {len(clips)} clipes.")
    return clips


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_exact_cross_split_duplicates(
    train_samples: Sequence[VideoSample], test_samples: Sequence[VideoSample]
) -> list[dict[str, str]]:
    log("Auditando duplicatas exatas entre Train e Test.")
    train_by_hash = {sha256_file(sample.video_path): sample.video_path for sample in train_samples}
    duplicates: list[dict[str, str]] = []
    for sample in test_samples:
        digest = sha256_file(sample.video_path)
        if digest in train_by_hash:
            duplicates.append(
                {
                    "sha256": digest,
                    "train_path": train_by_hash[digest],
                    "test_path": sample.video_path,
                }
            )
    return duplicates


def sample_frame_indices(start_frame: int, end_frame: int, num_frames: int) -> list[int]:
    total_frames = end_frame - start_frame + 1
    if total_frames <= 0:
        raise ValueError("Video sem frames.")
    if total_frames >= num_frames:
        return np.linspace(start_frame, end_frame, num_frames).astype(int).tolist()
    indices = list(range(start_frame, end_frame + 1))
    indices.extend([indices[-1]] * (num_frames - total_frames))
    return indices


def resize_frame_if_needed(frame: np.ndarray, max_side: int) -> np.ndarray:
    height, width = frame.shape[:2]
    longest_side = max(height, width)
    if max_side <= 0 or longest_side <= max_side:
        return frame
    scale = max_side / float(longest_side)
    return cv2.resize(
        frame,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def read_video_frames(
    video_path: str,
    num_frames: int,
    max_side: int,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> list[np.ndarray]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {video_path}")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        raise RuntimeError(f"Video invalido ou sem frames: {video_path}")

    first_frame = 0 if start_frame is None else max(0, start_frame)
    last_frame = total_frames - 1 if end_frame is None else min(total_frames - 1, end_frame)
    frames: list[np.ndarray] = []
    for frame_index in sample_frame_indices(first_frame, last_frame, num_frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame_bgr = cap.read()
        if not ok:
            break
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frames.append(resize_frame_if_needed(frame_rgb, max_side))
    cap.release()

    if not frames:
        raise RuntimeError(f"Nao foi possivel extrair frames: {video_path}")
    frames.extend([frames[-1]] * (num_frames - len(frames)))
    return frames[:num_frames]


class SCVDVideoDataset(Dataset):
    def __init__(self, samples: Sequence[VideoSample], processor, num_frames: int, max_frame_side: int):
        self.samples = list(samples)
        self.processor = processor
        self.num_frames = num_frames
        self.max_frame_side = max_frame_side

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict:
        sample = self.samples[index]
        frames = read_video_frames(
            sample.video_path,
            self.num_frames,
            self.max_frame_side,
            sample.start_frame,
            sample.end_frame,
        )
        inputs = self.processor(frames, return_tensors="pt")
        return {
            "pixel_values_videos": inputs["pixel_values_videos"].squeeze(0),
            "label": sample.label,
            "sample_id": sample.sample_id,
            "source_id": sample.source_id,
            "video_path": sample.video_path,
        }


def collate_video_batch(batch: Sequence[dict]) -> dict:
    return {
        "pixel_values_videos": torch.stack([item["pixel_values_videos"] for item in batch]),
        "labels": torch.tensor([item["label"] for item in batch], dtype=torch.long),
        "sample_ids": [item["sample_id"] for item in batch],
        "source_ids": [item["source_id"] for item in batch],
        "video_paths": [item["video_path"] for item in batch],
    }


class ClassifierHead(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, dropout: float, num_classes: int):
        super().__init__()
        self.network = nn.Sequential(
            nn.LayerNorm(input_dim),
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, num_classes),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


def feature_cache_matches(path: Path, samples: Sequence[VideoSample], args: argparse.Namespace) -> bool:
    if not path.exists():
        return False
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        return False
    expected_ids = [sample.sample_id for sample in samples]
    return (
        payload.get("model_name") == MODEL_NAME
        and payload.get("num_frames") == args.num_frames
        and payload.get("max_frame_side") == args.max_frame_side
        and payload.get("clip_duration_seconds") == args.clip_duration_seconds
        and payload.get("sample_ids") == expected_ids
    )


@torch.inference_mode()
def extract_features(
    name: str,
    samples: Sequence[VideoSample],
    processor,
    backbone: nn.Module,
    device: torch.device,
    args: argparse.Namespace,
    cache_path: Path,
) -> dict:
    if args.reuse_feature_cache and feature_cache_matches(cache_path, samples, args):
        log(f"Reutilizando embeddings de {name}: {cache_path}")
        return torch.load(cache_path, map_location="cpu", weights_only=True)

    dataset = SCVDVideoDataset(samples, processor, args.num_frames, args.max_frame_side)
    loader = DataLoader(
        dataset,
        batch_size=args.feature_batch_size,
        shuffle=False,
        num_workers=args.feature_workers,
        collate_fn=collate_video_batch,
        pin_memory=device.type == "cuda",
        persistent_workers=args.feature_workers > 0,
    )
    amp_enabled = device.type == "cuda" and not args.disable_amp
    amp_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    features: list[torch.Tensor] = []
    labels: list[torch.Tensor] = []
    sample_ids: list[str] = []
    source_ids: list[str] = []
    video_paths: list[str] = []

    backbone.eval()
    for step, batch in enumerate(loader, start=1):
        pixel_values = batch["pixel_values_videos"].to(device, non_blocking=True)
        with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=amp_enabled):
            outputs = backbone(pixel_values_videos=pixel_values, skip_predictor=True)
            batch_features = outputs.last_hidden_state.mean(dim=1)
        features.append(batch_features.float().cpu())
        labels.append(batch["labels"])
        sample_ids.extend(batch["sample_ids"])
        source_ids.extend(batch["source_ids"])
        video_paths.extend(batch["video_paths"])
        if step == 1 or step % args.log_every == 0 or step == len(loader):
            log(f"Embeddings {name}: batch {step}/{len(loader)}")

    payload = {
        "features": torch.cat(features),
        "labels": torch.cat(labels),
        "sample_ids": sample_ids,
        "source_ids": source_ids,
        "video_paths": video_paths,
        "model_name": MODEL_NAME,
        "num_frames": args.num_frames,
        "max_frame_side": args.max_frame_side,
        "clip_duration_seconds": args.clip_duration_seconds,
    }
    torch.save(payload, cache_path)
    log(f"Embeddings de {name} salvos em {cache_path}")
    return payload


def make_feature_loader(payload: dict, batch_size: int, shuffle: bool) -> DataLoader:
    dataset = TensorDataset(payload["features"], payload["labels"])
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)


def combine_feature_payloads(first: dict, second: dict) -> dict:
    return {
        "features": torch.cat([first["features"], second["features"]]),
        "labels": torch.cat([first["labels"], second["labels"]]),
    }


def compute_class_weights(labels: torch.Tensor, device: torch.device) -> torch.Tensor:
    counts = torch.bincount(labels, minlength=len(CLASS_NAMES)).float()
    weights = counts.sum() / (len(CLASS_NAMES) * counts.clamp_min(1))
    return weights.to(device)


def train_epoch(
    model: ClassifierHead,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
) -> tuple[float, float, float]:
    model.train()
    total_loss = 0.0
    labels_all: list[int] = []
    predictions_all: list[int] = []
    for features, labels in loader:
        features = features.to(device)
        labels = labels.to(device)
        optimizer.zero_grad(set_to_none=True)
        logits = model(features)
        loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * labels.size(0)
        labels_all.extend(labels.cpu().tolist())
        predictions_all.extend(logits.argmax(dim=1).cpu().tolist())
    accuracy = float(np.mean(np.equal(labels_all, predictions_all)))
    macro_f1 = float(f1_score(labels_all, predictions_all, average="macro", zero_division=0))
    return total_loss / len(labels_all), accuracy, macro_f1


@torch.inference_mode()
def evaluate_head(
    model: ClassifierHead,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> dict:
    model.eval()
    total_loss = 0.0
    labels_all: list[int] = []
    predictions_all: list[int] = []
    probabilities_all: list[list[float]] = []
    for features, labels in loader:
        features = features.to(device)
        labels = labels.to(device)
        logits = model(features)
        loss = criterion(logits, labels)
        probabilities = logits.softmax(dim=1)
        total_loss += loss.item() * labels.size(0)
        labels_all.extend(labels.cpu().tolist())
        predictions_all.extend(logits.argmax(dim=1).cpu().tolist())
        probabilities_all.extend(probabilities.cpu().tolist())
    return {
        "loss": total_loss / len(labels_all),
        "accuracy": float(np.mean(np.equal(labels_all, predictions_all))),
        "f1_macro": float(f1_score(labels_all, predictions_all, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(labels_all, predictions_all, average="weighted", zero_division=0)),
        "labels": labels_all,
        "predictions": predictions_all,
        "probabilities": probabilities_all,
        "classification_report": classification_report(
            labels_all,
            predictions_all,
            labels=list(range(len(CLASS_NAMES))),
            target_names=CLASS_NAMES,
            digits=4,
            zero_division=0,
            output_dict=True,
        ),
        "confusion_matrix": confusion_matrix(
            labels_all, predictions_all, labels=list(range(len(CLASS_NAMES)))
        ).tolist(),
    }


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def save_history_csv(path: Path, history: Sequence[EpochMetrics]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(history[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(item) for item in history)


def save_predictions_csv(path: Path, payload: dict, evaluation: dict) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["sample_id", "source_id", "video_path", "true_class", "predicted_class"] + [
            f"probability_{name}" for name in CLASS_NAMES
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, (label, prediction, probabilities) in enumerate(
            zip(evaluation["labels"], evaluation["predictions"], evaluation["probabilities"])
        ):
            row = {
                "sample_id": payload["sample_ids"][index],
                "source_id": payload["source_ids"][index],
                "video_path": payload["video_paths"][index],
                "true_class": CLASS_NAMES[label],
                "predicted_class": CLASS_NAMES[prediction],
            }
            row.update(
                {f"probability_{name}": probability for name, probability in zip(CLASS_NAMES, probabilities)}
            )
            writer.writerow(row)


def aggregate_evaluation_by_source(payload: dict, evaluation: dict) -> dict:
    grouped: dict[str, dict] = {}
    for source_id, label, probabilities in zip(
        payload["source_ids"], evaluation["labels"], evaluation["probabilities"]
    ):
        group = grouped.setdefault(source_id, {"label": label, "probabilities": []})
        if group["label"] != label:
            raise RuntimeError(f"Rotulos conflitantes para o video {source_id}")
        group["probabilities"].append(probabilities)
    labels = [group["label"] for group in grouped.values()]
    probabilities = [np.mean(group["probabilities"], axis=0).tolist() for group in grouped.values()]
    predictions = [int(np.argmax(values)) for values in probabilities]
    return {
        "accuracy": float(np.mean(np.equal(labels, predictions))),
        "f1_macro": float(f1_score(labels, predictions, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(labels, predictions, average="weighted", zero_division=0)),
        "labels": labels,
        "predictions": predictions,
        "probabilities": probabilities,
        "classification_report": classification_report(
            labels,
            predictions,
            labels=list(range(len(CLASS_NAMES))),
            target_names=CLASS_NAMES,
            digits=4,
            zero_division=0,
            output_dict=True,
        ),
        "confusion_matrix": confusion_matrix(
            labels, predictions, labels=list(range(len(CLASS_NAMES)))
        ).tolist(),
    }


def save_plots(output_dir: Path, history: Sequence[EpochMetrics], test_evaluation: dict) -> None:
    epochs = [item.epoch for item in history]
    figure, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    axes[0].plot(epochs, [item.train_loss for item in history], label="Treino")
    axes[0].plot(epochs, [item.val_loss for item in history], label="Validacao")
    axes[0].set(title="Loss", xlabel="Epoca", ylabel="Cross-entropy")
    axes[1].plot(epochs, [item.train_accuracy for item in history], label="Treino")
    axes[1].plot(epochs, [item.val_accuracy for item in history], label="Validacao")
    axes[1].set(title="Acuracia", xlabel="Epoca", ylabel="Acuracia", ylim=(0, 1.02))
    axes[2].plot(epochs, [item.train_f1_macro for item in history], label="Treino")
    axes[2].plot(epochs, [item.val_f1_macro for item in history], label="Validacao")
    axes[2].set(title="F1 macro", xlabel="Epoca", ylabel="F1", ylim=(0, 1.02))
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    figure.suptitle("Treinamento da cabeca classificadora - SCVD")
    figure.tight_layout()
    figure.savefig(output_dir / "training_curves.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    matrix = np.asarray(test_evaluation["confusion_matrix"])
    figure, axis = plt.subplots(figsize=(6.2, 5.2))
    image = axis.imshow(matrix, cmap="Blues")
    figure.colorbar(image, ax=axis)
    axis.set(
        title="Matriz de confusao - teste oficial",
        xlabel="Classe predita",
        ylabel="Classe real",
        xticks=range(len(CLASS_NAMES)),
        yticks=range(len(CLASS_NAMES)),
        xticklabels=CLASS_NAMES,
        yticklabels=CLASS_NAMES,
    )
    threshold = matrix.max() / 2 if matrix.size else 0
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            axis.text(
                column,
                row,
                str(matrix[row, column]),
                ha="center",
                va="center",
                color="white" if matrix[row, column] > threshold else "black",
            )
    figure.tight_layout()
    figure.savefig(output_dir / "confusion_matrix_test.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    per_class_f1 = [test_evaluation["classification_report"][name]["f1-score"] for name in CLASS_NAMES]
    figure, axis = plt.subplots(figsize=(7.2, 4.6))
    bars = axis.bar(CLASS_NAMES, per_class_f1, color=["#4C78A8", "#F58518", "#E45756"])
    axis.axhline(test_evaluation["f1_macro"], color="black", linestyle="--", label="F1 macro")
    axis.set(title="F1 por classe - teste oficial", ylabel="F1", ylim=(0, 1.05))
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    for bar, value in zip(bars, per_class_f1):
        axis.text(bar.get_x() + bar.get_width() / 2, value + 0.015, f"{value:.3f}", ha="center")
    figure.tight_layout()
    figure.savefig(output_dir / "f1_score_test.png", dpi=180, bbox_inches="tight")
    plt.close(figure)


def write_report(
    output_dir: Path,
    args: argparse.Namespace,
    split_summary: dict,
    best_epoch: int,
    val_evaluation: dict,
    test_evaluation: dict,
    test_video_evaluation: dict,
) -> None:
    report = test_evaluation["classification_report"]
    lines = [
        "# Treinamento da cabeça classificadora SCVD",
        "",
        "## Configuração",
        "",
        f"- Backbone congelado: `{MODEL_NAME}`",
        f"- Variante do dataset: `{args.dataset_variant}`",
        f"- Duplicatas exatas entre Train/Test: `{split_summary['exact_cross_split_duplicates']}`",
        f"- Frames por vídeo: `{args.num_frames}`",
        f"- Duração da janela: `{args.clip_duration_seconds}` segundo(s)",
        f"- Dimensão oculta da cabeça: `{args.hidden_dim}`",
        f"- Dropout: `{args.dropout}`",
        f"- Melhor época: `{best_epoch}`",
        f"- Refit final em todo o Train oficial: `{'não' if args.skip_refit_on_all_train else 'sim'}`",
        "",
        "## Divisões",
        "",
        f"- Treino: `{split_summary['train']}`",
        f"- Validação: `{split_summary['validation']}`",
        f"- Teste oficial: `{split_summary['test']}`",
        "",
        "## Desempenho",
        "",
        f"- Validação — acurácia: `{val_evaluation['accuracy']:.4f}`",
        f"- Validação — F1 macro: `{val_evaluation['f1_macro']:.4f}`",
        f"- Teste por clipe — acurácia: `{test_evaluation['accuracy']:.4f}`",
        f"- Teste por clipe — F1 macro: `{test_evaluation['f1_macro']:.4f}`",
        f"- Teste por clipe — F1 ponderado: `{test_evaluation['f1_weighted']:.4f}`",
        f"- Teste por vídeo — acurácia: `{test_video_evaluation['accuracy']:.4f}`",
        f"- Teste por vídeo — F1 macro: `{test_video_evaluation['f1_macro']:.4f}`",
        "",
        "### F1 por classe no teste (clipes)",
        "",
    ]
    for name in CLASS_NAMES:
        lines.append(f"- {name}: `{report[name]['f1-score']:.4f}` (suporte: `{int(report[name]['support'])}`)")
    lines.extend(
        [
            "",
            "## Artefatos",
            "",
            "- `best_scvd_classifier_head.pt`",
            "- `training_curves.png`",
            "- `confusion_matrix_test.png`",
            "- `f1_score_test.png`",
            "- `history.json` e `history.csv`",
            "- `test_metrics.json` e `test_predictions.csv`",
        ]
    )
    (output_dir / "training_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log(f"Device: {device}")
    log(f"Artefatos: {output_dir}")

    variant_root = resolve_variant_root(Path(args.dataset_root), args.dataset_variant)
    all_official_train = collect_split_samples(variant_root, "Train")
    all_official_test = collect_split_samples(variant_root, "Test")
    duplicates = find_exact_cross_split_duplicates(all_official_train, all_official_test)
    save_json(output_dir / "cross_split_duplicates.json", {"duplicates": duplicates})
    if duplicates and not args.allow_cross_split_duplicates:
        raise RuntimeError(
            f"Foram encontradas {len(duplicates)} duplicatas exatas entre Train e Test. "
            "A avaliacao teria vazamento. Use outra variante do dataset."
        )
    official_train_videos = limit_per_class(all_official_train, args.max_samples_per_class, args.seed)
    official_test_videos = limit_per_class(all_official_test, args.max_samples_per_class, args.seed + 1)
    train_videos, validation_videos = train_test_split(
        official_train_videos,
        test_size=args.val_size,
        random_state=args.seed,
        stratify=[sample.label for sample in official_train_videos],
    )
    train_samples = expand_videos_to_clips(
        train_videos, args.clip_duration_seconds, args.min_tail_fraction
    )
    validation_samples = expand_videos_to_clips(
        validation_videos, args.clip_duration_seconds, args.min_tail_fraction
    )
    official_test = expand_videos_to_clips(
        official_test_videos, args.clip_duration_seconds, args.min_tail_fraction
    )
    split_summary = {
        "train": {"videos": summarize(train_videos), "clips": summarize(train_samples)},
        "validation": {"videos": summarize(validation_videos), "clips": summarize(validation_samples)},
        "test": {"videos": summarize(official_test_videos), "clips": summarize(official_test)},
        "total": {
            "train": len(train_samples),
            "validation": len(validation_samples),
            "test": len(official_test),
        },
        "exact_cross_split_duplicates": len(duplicates),
    }
    save_json(output_dir / "split_summary.json", split_summary)
    log(f"Distribuicao: {split_summary}")

    log(f"Carregando processor e backbone congelado: {MODEL_NAME}")
    processor = AutoVideoProcessor.from_pretrained(MODEL_NAME, cache_dir=HF_CACHE_DIR)
    backbone = AutoModel.from_pretrained(MODEL_NAME, cache_dir=HF_CACHE_DIR).to(device)
    for parameter in backbone.parameters():
        parameter.requires_grad = False

    train_payload = extract_features(
        "treino", train_samples, processor, backbone, device, args, output_dir / "features_train.pt"
    )
    validation_payload = extract_features(
        "validacao",
        validation_samples,
        processor,
        backbone,
        device,
        args,
        output_dir / "features_validation.pt",
    )
    test_payload = extract_features(
        "teste", official_test, processor, backbone, device, args, output_dir / "features_test.pt"
    )
    del backbone
    if device.type == "cuda":
        torch.cuda.empty_cache()

    input_dim = int(train_payload["features"].shape[1])
    head = ClassifierHead(input_dim, args.hidden_dim, args.dropout, len(CLASS_NAMES)).to(device)
    class_weights = compute_class_weights(train_payload["labels"], device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(
        head.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    train_loader = make_feature_loader(train_payload, args.head_batch_size, shuffle=True)
    validation_loader = make_feature_loader(validation_payload, args.head_batch_size, shuffle=False)
    test_loader = make_feature_loader(test_payload, args.head_batch_size, shuffle=False)

    best_f1 = -1.0
    best_epoch = 0
    epochs_without_improvement = 0
    selection_path = output_dir / "best_validation_scvd_classifier_head.pt"
    history: list[EpochMetrics] = []
    for epoch in range(1, args.epochs + 1):
        train_loss, train_accuracy, train_f1_macro = train_epoch(
            head, train_loader, optimizer, criterion, device
        )
        validation_evaluation = evaluate_head(head, validation_loader, criterion, device)
        metrics = EpochMetrics(
            epoch=epoch,
            train_loss=train_loss,
            train_accuracy=train_accuracy,
            train_f1_macro=train_f1_macro,
            val_loss=validation_evaluation["loss"],
            val_accuracy=validation_evaluation["accuracy"],
            val_f1_macro=validation_evaluation["f1_macro"],
            val_f1_weighted=validation_evaluation["f1_weighted"],
        )
        history.append(metrics)
        log(
            f"Epoca {epoch:02d}/{args.epochs}: loss={train_loss:.4f}/{metrics.val_loss:.4f} "
            f"acc={train_accuracy:.4f}/{metrics.val_accuracy:.4f} "
            f"f1_macro={train_f1_macro:.4f}/{metrics.val_f1_macro:.4f}"
        )
        if metrics.val_f1_macro > best_f1 + 1e-6:
            best_f1 = metrics.val_f1_macro
            best_epoch = epoch
            epochs_without_improvement = 0
            torch.save(
                {
                    "head_state_dict": {key: value.detach().cpu() for key, value in head.state_dict().items()},
                    "model_name": MODEL_NAME,
                    "class_names": CLASS_NAMES,
                    "input_dim": input_dim,
                    "hidden_dim": args.hidden_dim,
                    "dropout": args.dropout,
                    "num_frames": args.num_frames,
                    "max_frame_side": args.max_frame_side,
                    "clip_duration_seconds": args.clip_duration_seconds,
                    "best_epoch": best_epoch,
                    "best_val_f1_macro": best_f1,
                },
                selection_path,
            )
            log(f"Novo melhor checkpoint: F1 macro={best_f1:.4f}")
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= args.patience:
                log(f"Early stopping apos {epoch} epocas.")
                break

    checkpoint = torch.load(selection_path, map_location=device, weights_only=True)
    head.load_state_dict(checkpoint["head_state_dict"])
    validation_evaluation = evaluate_head(head, validation_loader, criterion, device)

    if not args.skip_refit_on_all_train:
        log(f"Reajustando cabeca em Train+Validation por {best_epoch} epocas.")
        set_seed(args.seed)
        head = ClassifierHead(input_dim, args.hidden_dim, args.dropout, len(CLASS_NAMES)).to(device)
        combined_payload = combine_feature_payloads(train_payload, validation_payload)
        combined_loader = make_feature_loader(combined_payload, args.head_batch_size, shuffle=True)
        combined_weights = compute_class_weights(combined_payload["labels"], device)
        combined_criterion = nn.CrossEntropyLoss(weight=combined_weights)
        combined_optimizer = torch.optim.AdamW(
            head.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
        )
        for refit_epoch in range(1, best_epoch + 1):
            refit_loss, refit_accuracy, refit_f1 = train_epoch(
                head, combined_loader, combined_optimizer, combined_criterion, device
            )
            if refit_epoch == 1 or refit_epoch == best_epoch:
                log(
                    f"Refit {refit_epoch:02d}/{best_epoch}: loss={refit_loss:.4f} "
                    f"acc={refit_accuracy:.4f} f1_macro={refit_f1:.4f}"
                )
    test_evaluation = evaluate_head(head, test_loader, criterion, device)
    test_video_evaluation = aggregate_evaluation_by_source(test_payload, test_evaluation)

    final_path = output_dir / "best_scvd_classifier_head.pt"
    torch.save(
        {
            "head_state_dict": {key: value.detach().cpu() for key, value in head.state_dict().items()},
            "model_name": MODEL_NAME,
            "class_names": CLASS_NAMES,
            "input_dim": input_dim,
            "hidden_dim": args.hidden_dim,
            "dropout": args.dropout,
            "num_frames": args.num_frames,
            "max_frame_side": args.max_frame_side,
            "clip_duration_seconds": args.clip_duration_seconds,
            "selected_epoch": best_epoch,
            "best_val_f1_macro": best_f1,
            "refit_on_all_official_train": not args.skip_refit_on_all_train,
        },
        final_path,
    )

    save_json(output_dir / "history.json", {"epochs": [asdict(item) for item in history]})
    save_history_csv(output_dir / "history.csv", history)
    save_json(output_dir / "validation_metrics.json", validation_evaluation)
    save_json(output_dir / "test_metrics.json", test_evaluation)
    save_json(output_dir / "test_video_metrics.json", test_video_evaluation)
    save_predictions_csv(output_dir / "test_predictions.csv", test_payload, test_evaluation)
    save_plots(output_dir, history, test_evaluation)
    write_report(
        output_dir,
        args,
        split_summary,
        best_epoch,
        validation_evaluation,
        test_evaluation,
        test_video_evaluation,
    )
    log(
        f"Concluido: melhor epoca={best_epoch}, val_f1_macro={best_f1:.4f}, "
        f"test_clip_f1_macro={test_evaluation['f1_macro']:.4f}, "
        f"test_video_f1_macro={test_video_evaluation['f1_macro']:.4f}"
    )


if __name__ == "__main__":
    main()
