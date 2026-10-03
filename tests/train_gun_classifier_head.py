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
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader, Dataset, TensorDataset
from transformers import AutoModel, AutoVideoProcessor

matplotlib.use("Agg")
import matplotlib.pyplot as plt


MODEL_NAME = "facebook/vjepa2-vitl-fpc64-256"
CLASS_NAMES = ["sem_arma", "armado"]
RAW_CLASS_TO_LABEL = {"No_Gun": 0, "Handgun": 1, "Machine_Gun": 1}
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
    sample_id: str
    source_id: str
    raw_class: str
    label: int
    subject: str
    camera: str
    position: str
    start_frame: int | None = None
    end_frame: int | None = None


@dataclass
class EpochMetrics:
    epoch: int
    train_loss: float
    train_accuracy: float
    train_f1_armado: float
    val_loss: float
    val_accuracy_video: float
    val_f1_armado_video: float
    val_f1_macro_video: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Treina uma cabeca binaria V-JEPA 2 para detectar pessoas armadas."
    )
    parser.add_argument("--dataset-root", default=r"D:\Gun_Action_Recognition_Dataset")
    parser.add_argument("--output-dir", default="var/training_runs/gun_binary_head")
    parser.add_argument("--train-subjects", default="V1,V4")
    parser.add_argument("--validation-subjects", default="V3")
    parser.add_argument("--test-subjects", default="V2")
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--views-per-video", type=int, default=3)
    parser.add_argument("--view-duration-seconds", type=float, default=3.0)
    parser.add_argument("--feature-batch-size", type=int, default=2)
    parser.add_argument("--feature-workers", type=int, default=1)
    parser.add_argument("--head-batch-size", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--learning-rate", type=float, default=5e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-3)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.5)
    parser.add_argument("--max-frame-side", type=int, default=960)
    parser.add_argument("--log-every", type=int, default=100)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--reuse-feature-cache", action="store_true")
    parser.add_argument("--disable-amp", action="store_true")
    parser.add_argument("--skip-refit-on-all-train", action="store_true")
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_subjects(value: str) -> set[str]:
    subjects = {item.strip().upper() for item in value.split(",") if item.strip()}
    if not subjects:
        raise ValueError("A lista de sujeitos nao pode ser vazia.")
    return subjects


def resolve_dataset_root(root: Path) -> Path:
    nested = root / "Gun_Action_Recognition_Dataset"
    candidate = nested if nested.exists() else root
    missing = [name for name in RAW_CLASS_TO_LABEL if not (candidate / name).exists()]
    if missing:
        raise FileNotFoundError(f"Classes ausentes em {candidate}: {missing}")
    return candidate


def parse_sample_name(name: str) -> tuple[str, str, str]:
    parts = name.split("_")
    if len(parts) < 4:
        raise ValueError(f"Nome de amostra inesperado: {name}")
    return parts[1].upper(), parts[2].upper(), parts[3].upper()


def collect_videos(dataset_root: Path) -> list[VideoSample]:
    samples: list[VideoSample] = []
    for raw_class, label in RAW_CLASS_TO_LABEL.items():
        for sample_dir in sorted((dataset_root / raw_class).iterdir()):
            if not sample_dir.is_dir():
                continue
            video_path = sample_dir / "video.mp4"
            if not video_path.exists():
                raise FileNotFoundError(f"Video esperado nao encontrado: {video_path}")
            camera, position, subject = parse_sample_name(sample_dir.name)
            samples.append(
                VideoSample(
                    video_path=str(video_path),
                    sample_id=sample_dir.name,
                    source_id=f"{raw_class}:{sample_dir.name}",
                    raw_class=raw_class,
                    label=label,
                    subject=subject,
                    camera=camera,
                    position=position,
                )
            )
    if not samples:
        raise RuntimeError(f"Nenhum video encontrado em {dataset_root}")
    return samples


def split_by_subject(
    samples: Sequence[VideoSample],
    train_subjects: set[str],
    validation_subjects: set[str],
    test_subjects: set[str],
) -> tuple[list[VideoSample], list[VideoSample], list[VideoSample]]:
    overlap = (
        (train_subjects & validation_subjects)
        | (train_subjects & test_subjects)
        | (validation_subjects & test_subjects)
    )
    if overlap:
        raise ValueError(f"Sujeitos repetidos entre splits: {sorted(overlap)}")
    known = train_subjects | validation_subjects | test_subjects
    available = {sample.subject for sample in samples}
    if available - known:
        raise ValueError(f"Sujeitos sem split definido: {sorted(available - known)}")
    train = [sample for sample in samples if sample.subject in train_subjects]
    validation = [sample for sample in samples if sample.subject in validation_subjects]
    test = [sample for sample in samples if sample.subject in test_subjects]
    for name, split in (("train", train), ("validation", validation), ("test", test)):
        if set(sample.label for sample in split) != {0, 1}:
            raise ValueError(f"O split {name} precisa conter as duas classes binarias.")
    return train, validation, test


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_cross_split_duplicates(splits: dict[str, Sequence[VideoSample]]) -> list[dict[str, str]]:
    log("Auditando duplicatas exatas entre os splits.")
    seen: dict[str, tuple[str, str]] = {}
    duplicates: list[dict[str, str]] = []
    for split_name, samples in splits.items():
        for sample in samples:
            digest = sha256_file(sample.video_path)
            previous = seen.get(digest)
            if previous and previous[0] != split_name:
                duplicates.append(
                    {
                        "sha256": digest,
                        "first_split": previous[0],
                        "first_path": previous[1],
                        "second_split": split_name,
                        "second_path": sample.video_path,
                    }
                )
            else:
                seen[digest] = (split_name, sample.video_path)
    return duplicates


def expand_temporal_views(
    samples: Sequence[VideoSample], views_per_video: int, view_duration_seconds: float
) -> list[VideoSample]:
    if views_per_video <= 0:
        raise ValueError("--views-per-video precisa ser positivo.")
    views: list[VideoSample] = []
    for sample in samples:
        cap = cv2.VideoCapture(sample.video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Nao foi possivel abrir: {sample.video_path}")
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        cap.release()
        if total_frames <= 0 or fps <= 0:
            raise RuntimeError(f"Metadados invalidos: {sample.video_path}")
        window_frames = min(total_frames, max(1, int(round(fps * view_duration_seconds))))
        max_start = max(0, total_frames - window_frames)
        starts = np.linspace(0, max_start, views_per_video).round().astype(int).tolist()
        for view_index, start_frame in enumerate(starts):
            views.append(
                VideoSample(
                    video_path=sample.video_path,
                    sample_id=f"{sample.sample_id}:view{view_index}",
                    source_id=sample.source_id,
                    raw_class=sample.raw_class,
                    label=sample.label,
                    subject=sample.subject,
                    camera=sample.camera,
                    position=sample.position,
                    start_frame=start_frame,
                    end_frame=start_frame + window_frames - 1,
                )
            )
    return views


def summarize(samples: Sequence[VideoSample]) -> dict:
    binary = Counter(CLASS_NAMES[sample.label] for sample in samples)
    raw = Counter(sample.raw_class for sample in samples)
    subjects = Counter(sample.subject for sample in samples)
    return {
        "total": len(samples),
        "binary": dict(binary),
        "source_classes": dict(raw),
        "subjects": dict(subjects),
    }


def sample_frame_indices(start_frame: int, end_frame: int, num_frames: int) -> list[int]:
    count = end_frame - start_frame + 1
    if count <= 0:
        raise ValueError("Janela sem frames.")
    if count >= num_frames:
        return np.linspace(start_frame, end_frame, num_frames).astype(int).tolist()
    indices = list(range(start_frame, end_frame + 1))
    indices.extend([indices[-1]] * (num_frames - len(indices)))
    return indices


def resize_frame(frame: np.ndarray, max_side: int) -> np.ndarray:
    height, width = frame.shape[:2]
    longest = max(height, width)
    if max_side <= 0 or longest <= max_side:
        return frame
    scale = max_side / float(longest)
    return cv2.resize(
        frame,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def read_frames(sample: VideoSample, num_frames: int, max_side: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(sample.video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir: {sample.video_path}")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    start = 0 if sample.start_frame is None else max(0, sample.start_frame)
    end = total_frames - 1 if sample.end_frame is None else min(total_frames - 1, sample.end_frame)
    frames: list[np.ndarray] = []
    for frame_index in sample_frame_indices(start, end, num_frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame_bgr = cap.read()
        if not ok:
            break
        frames.append(resize_frame(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB), max_side))
    cap.release()
    if not frames:
        raise RuntimeError(f"Nenhum frame extraido: {sample.video_path}")
    frames.extend([frames[-1]] * (num_frames - len(frames)))
    return frames[:num_frames]


class GunVideoDataset(Dataset):
    def __init__(self, samples: Sequence[VideoSample], processor, num_frames: int, max_side: int):
        self.samples = list(samples)
        self.processor = processor
        self.num_frames = num_frames
        self.max_side = max_side

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict:
        sample = self.samples[index]
        frames = read_frames(sample, self.num_frames, self.max_side)
        inputs = self.processor(frames, return_tensors="pt")
        return {
            "pixel_values_videos": inputs["pixel_values_videos"].squeeze(0),
            "label": sample.label,
            "sample_id": sample.sample_id,
            "source_id": sample.source_id,
            "raw_class": sample.raw_class,
            "video_path": sample.video_path,
        }


def collate_video_batch(batch: Sequence[dict]) -> dict:
    return {
        "pixel_values_videos": torch.stack([item["pixel_values_videos"] for item in batch]),
        "labels": torch.tensor([item["label"] for item in batch], dtype=torch.long),
        "sample_ids": [item["sample_id"] for item in batch],
        "source_ids": [item["source_id"] for item in batch],
        "raw_classes": [item["raw_class"] for item in batch],
        "video_paths": [item["video_path"] for item in batch],
    }


class ArmedClassifierHead(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, dropout: float):
        super().__init__()
        self.network = nn.Sequential(
            nn.LayerNorm(input_dim),
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, len(CLASS_NAMES)),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


def cache_matches(path: Path, samples: Sequence[VideoSample], args: argparse.Namespace) -> bool:
    if not path.exists():
        return False
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        return False
    return (
        payload.get("model_name") == MODEL_NAME
        and payload.get("num_frames") == args.num_frames
        and payload.get("views_per_video") == args.views_per_video
        and payload.get("view_duration_seconds") == args.view_duration_seconds
        and payload.get("sample_ids") == [sample.sample_id for sample in samples]
    )


@torch.inference_mode()
def extract_features(
    split_name: str,
    samples: Sequence[VideoSample],
    processor,
    backbone: nn.Module,
    device: torch.device,
    args: argparse.Namespace,
    cache_path: Path,
) -> dict:
    if args.reuse_feature_cache and cache_matches(cache_path, samples, args):
        log(f"Reutilizando embeddings de {split_name}: {cache_path}")
        return torch.load(cache_path, map_location="cpu", weights_only=True)
    dataset = GunVideoDataset(samples, processor, args.num_frames, args.max_frame_side)
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
    raw_classes: list[str] = []
    video_paths: list[str] = []
    backbone.eval()
    for step, batch in enumerate(loader, start=1):
        pixels = batch["pixel_values_videos"].to(device, non_blocking=True)
        with torch.autocast(device_type=device.type, dtype=amp_dtype, enabled=amp_enabled):
            outputs = backbone(pixel_values_videos=pixels, skip_predictor=True)
            batch_features = outputs.last_hidden_state.mean(dim=1)
        features.append(batch_features.float().cpu())
        labels.append(batch["labels"])
        sample_ids.extend(batch["sample_ids"])
        source_ids.extend(batch["source_ids"])
        raw_classes.extend(batch["raw_classes"])
        video_paths.extend(batch["video_paths"])
        if step == 1 or step % args.log_every == 0 or step == len(loader):
            log(f"Embeddings {split_name}: batch {step}/{len(loader)}")
    payload = {
        "features": torch.cat(features),
        "labels": torch.cat(labels),
        "sample_ids": sample_ids,
        "source_ids": source_ids,
        "raw_classes": raw_classes,
        "video_paths": video_paths,
        "model_name": MODEL_NAME,
        "num_frames": args.num_frames,
        "views_per_video": args.views_per_video,
        "view_duration_seconds": args.view_duration_seconds,
    }
    torch.save(payload, cache_path)
    return payload


def feature_loader(payload: dict, batch_size: int, shuffle: bool) -> DataLoader:
    return DataLoader(
        TensorDataset(payload["features"], payload["labels"]),
        batch_size=batch_size,
        shuffle=shuffle,
    )


def combine_payloads(first: dict, second: dict) -> dict:
    return {
        "features": torch.cat([first["features"], second["features"]]),
        "labels": torch.cat([first["labels"], second["labels"]]),
    }


def class_weights(labels: torch.Tensor, device: torch.device) -> torch.Tensor:
    counts = torch.bincount(labels, minlength=len(CLASS_NAMES)).float()
    return (counts.sum() / (len(CLASS_NAMES) * counts.clamp_min(1))).to(device)


def binary_metrics(labels: Sequence[int], predictions: Sequence[int]) -> dict:
    return {
        "accuracy": float(np.mean(np.equal(labels, predictions))),
        "f1_armado": float(f1_score(labels, predictions, pos_label=1, zero_division=0)),
        "precision_armado": float(precision_score(labels, predictions, pos_label=1, zero_division=0)),
        "recall_armado": float(recall_score(labels, predictions, pos_label=1, zero_division=0)),
        "f1_macro": float(f1_score(labels, predictions, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(labels, predictions, average="weighted", zero_division=0)),
        "classification_report": classification_report(
            labels,
            predictions,
            labels=[0, 1],
            target_names=CLASS_NAMES,
            output_dict=True,
            digits=4,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(labels, predictions, labels=[0, 1]).tolist(),
    }


def train_epoch(
    model: ArmedClassifierHead,
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
    metrics = binary_metrics(labels_all, predictions_all)
    return total_loss / len(labels_all), metrics["accuracy"], metrics["f1_armado"]


@torch.inference_mode()
def evaluate(
    model: ArmedClassifierHead, loader: DataLoader, criterion: nn.Module, device: torch.device
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
        total_loss += criterion(logits, labels).item() * labels.size(0)
        probabilities = logits.softmax(dim=1)
        labels_all.extend(labels.cpu().tolist())
        predictions_all.extend(logits.argmax(dim=1).cpu().tolist())
        probabilities_all.extend(probabilities.cpu().tolist())
    result = binary_metrics(labels_all, predictions_all)
    result.update(
        {
            "loss": total_loss / len(labels_all),
            "labels": labels_all,
            "predictions": predictions_all,
            "probabilities": probabilities_all,
        }
    )
    return result


def aggregate_by_video(payload: dict, evaluation: dict) -> dict:
    grouped: dict[str, dict] = {}
    for source_id, raw_class, label, probabilities in zip(
        payload["source_ids"],
        payload["raw_classes"],
        evaluation["labels"],
        evaluation["probabilities"],
    ):
        group = grouped.setdefault(
            source_id, {"label": label, "raw_class": raw_class, "probabilities": []}
        )
        group["probabilities"].append(probabilities)
    labels = [group["label"] for group in grouped.values()]
    raw_classes = [group["raw_class"] for group in grouped.values()]
    probabilities = [np.mean(group["probabilities"], axis=0).tolist() for group in grouped.values()]
    predictions = [int(np.argmax(item)) for item in probabilities]
    result = binary_metrics(labels, predictions)
    result.update(
        {
            "source_ids": list(grouped),
            "raw_classes": raw_classes,
            "labels": labels,
            "predictions": predictions,
            "probabilities": probabilities,
            "recall_by_source_class": {
                raw_class: float(
                    recall_score(
                        [1 if item == raw_class else 0 for item in raw_classes],
                        [
                            1 if item == raw_class and prediction == RAW_CLASS_TO_LABEL[raw_class] else 0
                            for item, prediction in zip(raw_classes, predictions)
                        ],
                        zero_division=0,
                    )
                )
                for raw_class in RAW_CLASS_TO_LABEL
            },
        }
    )
    return result


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_history_csv(path: Path, history: Sequence[EpochMetrics]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(history[0])))
        writer.writeheader()
        writer.writerows(asdict(item) for item in history)


def save_predictions(path: Path, payload: dict, evaluation: dict) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        fields = [
            "source_id",
            "source_class",
            "true_class",
            "predicted_class",
            "probability_sem_arma",
            "probability_armado",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for source_id, raw_class, label, prediction, probabilities in zip(
            evaluation["source_ids"],
            evaluation["raw_classes"],
            evaluation["labels"],
            evaluation["predictions"],
            evaluation["probabilities"],
        ):
            writer.writerow(
                {
                    "source_id": source_id,
                    "source_class": raw_class,
                    "true_class": CLASS_NAMES[label],
                    "predicted_class": CLASS_NAMES[prediction],
                    "probability_sem_arma": probabilities[0],
                    "probability_armado": probabilities[1],
                }
            )


def save_plots(output_dir: Path, history: Sequence[EpochMetrics], test_metrics: dict) -> None:
    epochs = [item.epoch for item in history]
    figure, axes = plt.subplots(1, 3, figsize=(16, 4.6))
    axes[0].plot(epochs, [item.train_loss for item in history], label="Treino")
    axes[0].plot(epochs, [item.val_loss for item in history], label="Validacao")
    axes[0].set(title="Loss", xlabel="Epoca", ylabel="Cross-entropy")
    axes[1].plot(epochs, [item.train_accuracy for item in history], label="Treino (clipes)")
    axes[1].plot(epochs, [item.val_accuracy_video for item in history], label="Validacao (videos)")
    axes[1].set(title="Acuracia", xlabel="Epoca", ylabel="Acuracia", ylim=(0, 1.02))
    axes[2].plot(epochs, [item.train_f1_armado for item in history], label="Treino (clipes)")
    axes[2].plot(epochs, [item.val_f1_armado_video for item in history], label="Validacao (videos)")
    axes[2].set(title="F1 armado", xlabel="Epoca", ylabel="F1", ylim=(0, 1.02))
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend()
    figure.suptitle("Cabeca binaria de deteccao de pessoa armada")
    figure.tight_layout()
    figure.savefig(output_dir / "training_curves.png", dpi=180, bbox_inches="tight")
    plt.close(figure)

    matrix = np.asarray(test_metrics["confusion_matrix"])
    figure, axis = plt.subplots(figsize=(5.8, 5.0))
    image = axis.imshow(matrix, cmap="Blues")
    figure.colorbar(image, ax=axis)
    axis.set(
        title="Matriz de confusao - teste por pessoa",
        xlabel="Classe predita",
        ylabel="Classe real",
        xticks=[0, 1],
        yticks=[0, 1],
        xticklabels=CLASS_NAMES,
        yticklabels=CLASS_NAMES,
    )
    threshold = matrix.max() / 2
    for row in range(2):
        for column in range(2):
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

    report = test_metrics["classification_report"]
    values = [report[name]["f1-score"] for name in CLASS_NAMES]
    figure, axis = plt.subplots(figsize=(6.5, 4.6))
    bars = axis.bar(CLASS_NAMES, values, color=["#4C78A8", "#E45756"])
    axis.axhline(test_metrics["f1_macro"], color="black", linestyle="--", label="F1 macro")
    axis.set(title="F1 por classe - teste por pessoa", ylabel="F1", ylim=(0, 1.05))
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    for bar, value in zip(bars, values):
        axis.text(bar.get_x() + bar.get_width() / 2, value + 0.015, f"{value:.3f}", ha="center")
    figure.tight_layout()
    figure.savefig(output_dir / "f1_score_test.png", dpi=180, bbox_inches="tight")
    plt.close(figure)


def write_report(
    output_dir: Path,
    args: argparse.Namespace,
    split_summary: dict,
    best_epoch: int,
    best_val_metrics: dict,
    test_metrics: dict,
) -> None:
    report = test_metrics["classification_report"]
    subtype = test_metrics["recall_by_source_class"]
    lines = [
        "# Cabeça binária para detecção de pessoa armada",
        "",
        "## Formulação",
        "",
        "- `No_Gun` → `sem_arma`",
        "- `Handgun` + `Machine_Gun` → `armado`",
        f"- Backbone congelado: `{MODEL_NAME}`",
        f"- Views por vídeo: `{args.views_per_video}` de `{args.view_duration_seconds}` segundos",
        f"- Frames por view: `{args.num_frames}`",
        "- Split por pessoa: treino `V1,V4`, validação `V3`, teste `V2`",
        f"- Melhor época: `{best_epoch}`",
        f"- Refit em treino+validação: `{'não' if args.skip_refit_on_all_train else 'sim'}`",
        "",
        "## Divisões",
        "",
        f"- Treino: `{split_summary['train_videos']}`",
        f"- Validação: `{split_summary['validation_videos']}`",
        f"- Teste: `{split_summary['test_videos']}`",
        f"- Duplicatas exatas entre splits: `{split_summary['cross_split_duplicates']}`",
        "",
        "## Resultados",
        "",
        f"- Validação — F1 armado por vídeo: `{best_val_metrics['f1_armado']:.4f}`",
        f"- Teste — acurácia por vídeo: `{test_metrics['accuracy']:.4f}`",
        f"- Teste — F1 armado: `{test_metrics['f1_armado']:.4f}`",
        f"- Teste — precisão armado: `{test_metrics['precision_armado']:.4f}`",
        f"- Teste — recall armado: `{test_metrics['recall_armado']:.4f}`",
        f"- Teste — F1 macro: `{test_metrics['f1_macro']:.4f}`",
        f"- F1 sem arma: `{report['sem_arma']['f1-score']:.4f}`",
        f"- F1 armado: `{report['armado']['f1-score']:.4f}`",
        f"- Recall Handgun: `{subtype['Handgun']:.4f}`",
        f"- Recall Machine_Gun: `{subtype['Machine_Gun']:.4f}`",
        "",
        "## Artefatos",
        "",
        "- `best_gun_binary_classifier_head.pt`",
        "- `training_curves.png`",
        "- `confusion_matrix_test.png`",
        "- `f1_score_test.png`",
        "- `history.json`, `test_metrics.json` e `test_predictions.csv`",
    ]
    (output_dir / "training_report.md").write_text("\n".join(lines), encoding="utf-8")


def checkpoint_payload(
    head: ArmedClassifierHead, args: argparse.Namespace, input_dim: int, best_epoch: int, best_f1: float, refit: bool
) -> dict:
    return {
        "head_state_dict": {key: value.detach().cpu() for key, value in head.state_dict().items()},
        "model_name": MODEL_NAME,
        "class_names": CLASS_NAMES,
        "source_class_mapping": RAW_CLASS_TO_LABEL,
        "input_dim": input_dim,
        "hidden_dim": args.hidden_dim,
        "dropout": args.dropout,
        "num_frames": args.num_frames,
        "views_per_video": args.views_per_video,
        "view_duration_seconds": args.view_duration_seconds,
        "selected_epoch": best_epoch,
        "best_val_f1_armado": best_f1,
        "refit_on_train_and_validation": refit,
        "split_subjects": {
            "train": sorted(parse_subjects(args.train_subjects)),
            "validation": sorted(parse_subjects(args.validation_subjects)),
            "test": sorted(parse_subjects(args.test_subjects)),
        },
    }


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log(f"Device: {device}")
    dataset_root = resolve_dataset_root(Path(args.dataset_root))
    videos = collect_videos(dataset_root)
    train_videos, validation_videos, test_videos = split_by_subject(
        videos,
        parse_subjects(args.train_subjects),
        parse_subjects(args.validation_subjects),
        parse_subjects(args.test_subjects),
    )
    duplicates = audit_cross_split_duplicates(
        {"train": train_videos, "validation": validation_videos, "test": test_videos}
    )
    save_json(output_dir / "cross_split_duplicates.json", {"duplicates": duplicates})
    if duplicates:
        raise RuntimeError(f"Encontradas {len(duplicates)} duplicatas exatas entre splits.")

    train_views = expand_temporal_views(train_videos, args.views_per_video, args.view_duration_seconds)
    validation_views = expand_temporal_views(
        validation_videos, args.views_per_video, args.view_duration_seconds
    )
    test_views = expand_temporal_views(test_videos, args.views_per_video, args.view_duration_seconds)
    split_summary = {
        "train_videos": summarize(train_videos),
        "validation_videos": summarize(validation_videos),
        "test_videos": summarize(test_videos),
        "train_views": summarize(train_views),
        "validation_views": summarize(validation_views),
        "test_views": summarize(test_views),
        "cross_split_duplicates": len(duplicates),
    }
    save_json(output_dir / "split_summary.json", split_summary)
    log(f"Splits: {split_summary}")

    processor = AutoVideoProcessor.from_pretrained(MODEL_NAME, cache_dir=HF_CACHE_DIR)
    backbone = AutoModel.from_pretrained(MODEL_NAME, cache_dir=HF_CACHE_DIR).to(device)
    for parameter in backbone.parameters():
        parameter.requires_grad = False
    train_payload = extract_features(
        "treino", train_views, processor, backbone, device, args, output_dir / "features_train.pt"
    )
    validation_payload = extract_features(
        "validacao",
        validation_views,
        processor,
        backbone,
        device,
        args,
        output_dir / "features_validation.pt",
    )
    test_payload = extract_features(
        "teste", test_views, processor, backbone, device, args, output_dir / "features_test.pt"
    )
    del backbone
    if device.type == "cuda":
        torch.cuda.empty_cache()

    input_dim = int(train_payload["features"].shape[1])
    head = ArmedClassifierHead(input_dim, args.hidden_dim, args.dropout).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights(train_payload["labels"], device))
    optimizer = torch.optim.AdamW(
        head.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
    )
    train_loader = feature_loader(train_payload, args.head_batch_size, True)
    validation_loader = feature_loader(validation_payload, args.head_batch_size, False)
    test_loader = feature_loader(test_payload, args.head_batch_size, False)

    history: list[EpochMetrics] = []
    best_f1 = -1.0
    best_epoch = 0
    best_val_metrics: dict | None = None
    without_improvement = 0
    selection_path = output_dir / "best_validation_gun_binary_classifier_head.pt"
    for epoch in range(1, args.epochs + 1):
        train_loss, train_accuracy, train_f1 = train_epoch(
            head, train_loader, optimizer, criterion, device
        )
        val_clip_metrics = evaluate(head, validation_loader, criterion, device)
        val_video_metrics = aggregate_by_video(validation_payload, val_clip_metrics)
        history.append(
            EpochMetrics(
                epoch=epoch,
                train_loss=train_loss,
                train_accuracy=train_accuracy,
                train_f1_armado=train_f1,
                val_loss=val_clip_metrics["loss"],
                val_accuracy_video=val_video_metrics["accuracy"],
                val_f1_armado_video=val_video_metrics["f1_armado"],
                val_f1_macro_video=val_video_metrics["f1_macro"],
            )
        )
        log(
            f"Epoca {epoch:02d}: loss={train_loss:.4f}/{val_clip_metrics['loss']:.4f} "
            f"f1_armado={train_f1:.4f}/{val_video_metrics['f1_armado']:.4f} "
            f"val_f1_macro={val_video_metrics['f1_macro']:.4f}"
        )
        if val_video_metrics["f1_armado"] > best_f1 + 1e-6:
            best_f1 = val_video_metrics["f1_armado"]
            best_epoch = epoch
            best_val_metrics = val_video_metrics
            without_improvement = 0
            torch.save(
                checkpoint_payload(head, args, input_dim, best_epoch, best_f1, False), selection_path
            )
        else:
            without_improvement += 1
            if without_improvement >= args.patience:
                log(f"Early stopping na epoca {epoch}.")
                break

    if best_val_metrics is None:
        raise RuntimeError("Nenhum checkpoint foi selecionado.")
    selection = torch.load(selection_path, map_location=device, weights_only=True)
    head.load_state_dict(selection["head_state_dict"])

    if not args.skip_refit_on_all_train:
        log(f"Refit em treino+validacao por {best_epoch} epocas.")
        set_seed(args.seed)
        head = ArmedClassifierHead(input_dim, args.hidden_dim, args.dropout).to(device)
        combined = combine_payloads(train_payload, validation_payload)
        combined_loader = feature_loader(combined, args.head_batch_size, True)
        combined_criterion = nn.CrossEntropyLoss(weight=class_weights(combined["labels"], device))
        combined_optimizer = torch.optim.AdamW(
            head.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
        )
        for refit_epoch in range(1, best_epoch + 1):
            loss, accuracy, f1_armado = train_epoch(
                head, combined_loader, combined_optimizer, combined_criterion, device
            )
            if refit_epoch in (1, best_epoch):
                log(
                    f"Refit {refit_epoch:02d}/{best_epoch}: loss={loss:.4f} "
                    f"acc={accuracy:.4f} f1_armado={f1_armado:.4f}"
                )

    test_clip_metrics = evaluate(head, test_loader, criterion, device)
    test_video_metrics = aggregate_by_video(test_payload, test_clip_metrics)
    torch.save(
        checkpoint_payload(
            head,
            args,
            input_dim,
            best_epoch,
            best_f1,
            not args.skip_refit_on_all_train,
        ),
        output_dir / "best_gun_binary_classifier_head.pt",
    )
    save_json(output_dir / "history.json", {"epochs": [asdict(item) for item in history]})
    save_history_csv(output_dir / "history.csv", history)
    save_json(output_dir / "best_validation_metrics.json", best_val_metrics)
    save_json(output_dir / "test_clip_metrics.json", test_clip_metrics)
    save_json(output_dir / "test_metrics.json", test_video_metrics)
    save_predictions(output_dir / "test_predictions.csv", test_payload, test_video_metrics)
    save_plots(output_dir, history, test_video_metrics)
    write_report(output_dir, args, split_summary, best_epoch, best_val_metrics, test_video_metrics)
    log(
        f"Concluido: best_epoch={best_epoch} val_f1_armado={best_f1:.4f} "
        f"test_f1_armado={test_video_metrics['f1_armado']:.4f} "
        f"test_recall_armado={test_video_metrics['recall_armado']:.4f}"
    )


if __name__ == "__main__":
    main()
