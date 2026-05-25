from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import cv2
import matplotlib
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import classification_report, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from transformers import AutoModel, AutoVideoProcessor

matplotlib.use("Agg")
import matplotlib.pyplot as plt


MODEL_NAME = "facebook/vjepa2-vitl-fpc64-256"
CLASS_NAMES = ["sem_queda", "queda"]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
DEFAULT_SEED = 42
HF_CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "huggingface"
HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(HF_CACHE_DIR))
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_CACHE_DIR / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(HF_CACHE_DIR / "transformers"))
DEFAULT_WORKERS = 2 if os.name == "nt" else min(8, max(2, (os.cpu_count() or 4) // 2))
DEFAULT_VAL_WORKERS = 0 if os.name == "nt" else DEFAULT_WORKERS


def log(message: str):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


@dataclass(frozen=True)
class VideoSample:
    video_path: str
    label: int
    dataset_name: str
    group_id: str
    sample_id: str
    start_frame: int | None = None
    end_frame: int | None = None


@dataclass
class EpochMetrics:
    epoch_index: int
    phase_name: str
    train_loss: float
    train_acc: float
    val_loss: float
    val_acc: float
    val_f1_queda: float
    val_recall_queda: float
    val_f1_macro: float
    val_recall_macro: float


def parse_args():
    parser = argparse.ArgumentParser(
        description="Treina um classificador V-JEPA 2 usando os datasets archive e Fall Vision."
    )
    parser.add_argument("--archive-root", default="datasets/archive")
    parser.add_argument("--fall-vision-root", default="datasets/Fall Vision")
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--phase1-epochs", type=int, default=5)
    parser.add_argument("--phase2-epochs", type=int, default=15)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--head-lr", type=float, default=1e-3)
    parser.add_argument("--backbone-lr", type=float, default=1e-5)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--num-workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--val-num-workers", type=int, default=DEFAULT_VAL_WORKERS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-samples-per-dataset", type=int, default=0)
    parser.add_argument("--max-frame-side", type=int, default=960)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--accumulation-steps", type=int, default=1)
    parser.add_argument("--backbone-trainable-fraction", type=float, default=0.15)
    parser.add_argument("--disable-amp", action="store_true")
    parser.add_argument("--disable-sampler", action="store_true")
    parser.add_argument("--compile-model", action="store_true")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--output-checkpoint", default="best_vjepa2_fall_classifier_combined.pt")
    return parser.parse_args()


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def sample_frame_indices(start_frame: int, end_frame: int, num_frames: int) -> list[int]:
    total_frames = end_frame - start_frame + 1
    if total_frames <= 0:
        raise ValueError("Video sem frames.")

    if total_frames < num_frames:
        indices = np.linspace(start_frame, end_frame, total_frames).astype(int).tolist()
        while len(indices) < num_frames:
            indices.append(indices[-1])
        return indices[:num_frames]

    return np.linspace(start_frame, end_frame, num_frames).astype(int).tolist()


def read_video_frames_opencv(
    video_path: str,
    num_frames: int,
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

    start_idx = 0 if start_frame is None else max(0, start_frame)
    end_idx = total_frames - 1 if end_frame is None else min(total_frames - 1, end_frame)
    if end_idx < start_idx:
        cap.release()
        raise RuntimeError(f"Janela de frames invalida em: {video_path}")

    target_indices = sample_frame_indices(start_idx, end_idx, num_frames)
    frames = []
    for frame_idx in target_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame_bgr = cap.read()
        if not ret:
            break
        frames.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))

    cap.release()
    if not frames:
        raise RuntimeError(f"Nao foi possivel extrair frames: {video_path}")

    while len(frames) < num_frames:
        frames.append(frames[-1])

    return frames[:num_frames]


def normalize_mcfd_cam(chute: int, cam_raw: str, start_frame: int, end_frame: int) -> int:
    cam = int(float(cam_raw))
    if 1 <= cam <= 8:
        return cam
    if chute == 23 and cam == 55 and start_frame == 1572 and end_frame == 1602:
        log("Corrigindo typo conhecido do CSV: chute23 cam55 -> cam3")
        return 3
    raise ValueError(
        f"Valor de camera invalido no CSV: chute={chute} cam={cam_raw} start={start_frame} end={end_frame}"
    )


def canonical_fall_vision_id(video_path: Path) -> str:
    stem = video_path.stem.lower()
    for suffix in ("_resized", "_anonymized"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem


def collect_archive_samples(dataset_root: Path) -> list[VideoSample]:
    metadata_path = dataset_root / "data_tuple3.csv"
    video_root = dataset_root / "dataset" / "dataset"
    if not metadata_path.exists():
        raise FileNotFoundError(f"CSV de anotacao nao encontrado: {metadata_path}")
    if not video_root.exists():
        raise FileNotFoundError(f"Diretorio de videos nao encontrado: {video_root}")

    samples = []
    with metadata_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            chute = int(float(row["chute"]))
            start_frame = int(float(row["start"]))
            end_frame = int(float(row["end"]))
            cam = normalize_mcfd_cam(chute, row["cam"], start_frame, end_frame)
            label_id = int(float(row["label"]))
            video_path = video_root / f"chute{chute:02d}" / f"cam{cam}.avi"
            if not video_path.exists():
                raise FileNotFoundError(f"Video anotado nao encontrado: {video_path}")

            group_id = f"archive:chute{chute:02d}"
            sample_id = f"{group_id}:cam{cam}:{start_frame}-{end_frame}"
            samples.append(
                VideoSample(
                    video_path=str(video_path),
                    label=label_id,
                    dataset_name="archive",
                    group_id=group_id,
                    sample_id=sample_id,
                    start_frame=start_frame,
                    end_frame=end_frame,
                )
            )
    return samples


def collect_fall_vision_samples(dataset_root: Path) -> list[VideoSample]:
    nested_root = dataset_root / "Fall Vision"
    base_root = nested_root if nested_root.exists() else dataset_root
    samples = []
    for label_name, folder_name in (("queda", "fall"), ("sem_queda", "no_fall")):
        class_root = base_root / folder_name
        if not class_root.exists():
            raise FileNotFoundError(f"Pasta esperada nao encontrada: {class_root}")
        for video_path in class_root.rglob("*"):
            if video_path.suffix.lower() not in VIDEO_SUFFIXES:
                continue
            relative_parts = video_path.relative_to(class_root).parts
            subset = relative_parts[0] if len(relative_parts) > 1 else "default"
            canonical_id = canonical_fall_vision_id(video_path)
            group_id = f"fall_vision:{subset}:{canonical_id}"
            sample_id = f"{group_id}:{video_path.name}"
            samples.append(
                VideoSample(
                    video_path=str(video_path),
                    label=CLASS_TO_ID[label_name],
                    dataset_name="fall_vision",
                    group_id=group_id,
                    sample_id=sample_id,
                )
            )
    return samples


def maybe_limit_samples(samples: Sequence[VideoSample], max_samples: int, seed: int) -> list[VideoSample]:
    if max_samples <= 0 or len(samples) <= max_samples:
        return list(samples)

    by_label = defaultdict(list)
    for sample in samples:
        by_label[sample.label].append(sample)

    rng = random.Random(seed)
    limited = []
    labels = sorted(by_label)
    per_label = max_samples // len(labels)
    remainder = max_samples % len(labels)
    for index, label in enumerate(labels):
        label_samples = list(by_label[label])
        rng.shuffle(label_samples)
        take = per_label + (1 if index < remainder else 0)
        limited.extend(label_samples[:take])
    rng.shuffle(limited)
    return limited


def split_dataset_samples(samples: Sequence[VideoSample], val_size: float, seed: int) -> tuple[list[VideoSample], list[VideoSample]]:
    labels = [sample.label for sample in samples]
    groups = [sample.group_id for sample in samples]
    splitter = GroupShuffleSplit(n_splits=1, test_size=val_size, random_state=seed)
    train_idx, val_idx = next(splitter.split(np.zeros(len(samples)), labels, groups))
    train_samples = [samples[index] for index in train_idx]
    val_samples = [samples[index] for index in val_idx]
    return train_samples, val_samples


def summarize_samples(samples: Sequence[VideoSample]) -> dict:
    by_dataset = defaultdict(Counter)
    total = Counter()
    for sample in samples:
        by_dataset[sample.dataset_name][sample.label] += 1
        total[sample.label] += 1
    return {
        "total": {CLASS_NAMES[label]: int(count) for label, count in total.items()},
        "by_dataset": {
            dataset_name: {CLASS_NAMES[label]: int(count) for label, count in counter.items()}
            for dataset_name, counter in by_dataset.items()
        },
    }


def resize_frame_if_needed(frame: np.ndarray, max_side: int) -> np.ndarray:
    height, width = frame.shape[:2]
    longest_side = max(height, width)
    if max_side <= 0 or longest_side <= max_side:
        return frame

    scale = max_side / float(longest_side)
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    return cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_AREA)


def preprocess_frames(frames: list[np.ndarray], max_side: int) -> list[np.ndarray]:
    return [resize_frame_if_needed(frame, max_side=max_side) for frame in frames]


def apply_frame_augmentations(frames: list[np.ndarray]) -> list[np.ndarray]:
    if random.random() < 0.5:
        frames = [np.ascontiguousarray(frame[:, ::-1]) for frame in frames]
    if random.random() < 0.35:
        alpha = random.uniform(0.9, 1.1)
        beta = random.uniform(-10.0, 10.0)
        frames = [cv2.convertScaleAbs(frame, alpha=alpha, beta=beta) for frame in frames]
    return frames


class VideoClassificationDataset(Dataset):
    def __init__(self, samples: Sequence[VideoSample], processor, num_frames: int, augment: bool, max_frame_side: int):
        self.samples = list(samples)
        self.processor = processor
        self.num_frames = num_frames
        self.augment = augment
        self.max_frame_side = max_frame_side

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        sample = self.samples[idx]
        frames = read_video_frames_opencv(
            sample.video_path,
            self.num_frames,
            start_frame=sample.start_frame,
            end_frame=sample.end_frame,
        )
        frames = preprocess_frames(frames, max_side=self.max_frame_side)
        if self.augment:
            frames = apply_frame_augmentations(frames)
        inputs = self.processor(frames, return_tensors="pt")
        return {
            "pixel_values_videos": inputs["pixel_values_videos"].squeeze(0),
            "labels": torch.tensor(sample.label, dtype=torch.long),
            "dataset_names": sample.dataset_name,
            "sample_ids": sample.sample_id,
        }


def collate_fn(batch):
    return {
        "pixel_values_videos": torch.stack([item["pixel_values_videos"] for item in batch], dim=0),
        "labels": torch.stack([item["labels"] for item in batch], dim=0),
        "dataset_names": [item["dataset_names"] for item in batch],
        "sample_ids": [item["sample_ids"] for item in batch],
    }


class VJEPA2Classifier(nn.Module):
    def __init__(self, model_name: str, num_classes: int, cache_dir: str | Path | None = None):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(model_name, cache_dir=cache_dir or HF_CACHE_DIR)
        hidden_size = self.backbone.config.hidden_size
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(512, num_classes),
        )

    def forward(self, pixel_values_videos):
        outputs = self.backbone(pixel_values_videos=pixel_values_videos, skip_predictor=True)
        features = outputs.last_hidden_state.mean(dim=1)
        return self.classifier(features)


def freeze_backbone(model: VJEPA2Classifier):
    for parameter in model.backbone.parameters():
        parameter.requires_grad = False
    for parameter in model.classifier.parameters():
        parameter.requires_grad = True


def unfreeze_backbone_tail(model: VJEPA2Classifier, trainable_fraction: float):
    freeze_backbone(model)
    if trainable_fraction <= 0:
        return

    named_parameters = list(model.backbone.named_parameters())
    trainable_count = max(1, int(len(named_parameters) * trainable_fraction))
    for _, parameter in named_parameters[-trainable_count:]:
        parameter.requires_grad = True


def build_optimizer(model: VJEPA2Classifier, head_lr: float, backbone_lr: float, weight_decay: float):
    head_params = [parameter for parameter in model.classifier.parameters() if parameter.requires_grad]
    backbone_params = [parameter for parameter in model.backbone.parameters() if parameter.requires_grad]
    param_groups = []
    if head_params:
        param_groups.append({"params": head_params, "lr": head_lr})
    if backbone_params:
        param_groups.append({"params": backbone_params, "lr": backbone_lr})
    return torch.optim.AdamW(param_groups, weight_decay=weight_decay)


def create_train_sampler(samples: Sequence[VideoSample]) -> WeightedRandomSampler:
    label_counts = Counter(sample.label for sample in samples)
    dataset_counts = Counter(sample.dataset_name for sample in samples)
    weights = []
    for sample in samples:
        label_weight = 1.0 / label_counts[sample.label]
        dataset_weight = 1.0 / dataset_counts[sample.dataset_name]
        weights.append(label_weight * dataset_weight)
    return WeightedRandomSampler(weights=torch.DoubleTensor(weights), num_samples=len(weights), replacement=True)


def infer_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def build_dataloader(dataset, batch_size: int, num_workers: int, shuffle: bool, sampler=None):
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle if sampler is None else False,
        sampler=sampler,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
        persistent_workers=num_workers > 0,
        prefetch_factor=4 if num_workers > 0 else None,
        collate_fn=collate_fn,
    )


def compute_class_weights(samples: Sequence[VideoSample], device: torch.device) -> torch.Tensor:
    counts = Counter(sample.label for sample in samples)
    total = sum(counts.values())
    weights = []
    for label in range(len(CLASS_NAMES)):
        class_count = counts.get(label, 1)
        weights.append(total / (len(CLASS_NAMES) * class_count))
    return torch.tensor(weights, dtype=torch.float32, device=device)


def train_one_epoch(
    model,
    dataloader,
    optimizer,
    criterion,
    device,
    scaler,
    accumulation_steps: int,
    amp_enabled: bool,
    log_every: int,
):
    model.train()
    total_loss = 0.0
    total_correct = 0
    total_samples = 0
    optimizer.zero_grad(set_to_none=True)

    for step, batch in enumerate(dataloader, start=1):
        pixel_values = batch["pixel_values_videos"].to(device, non_blocking=True)
        labels = batch["labels"].to(device, non_blocking=True)

        with torch.amp.autocast(device_type=device.type, enabled=amp_enabled):
            logits = model(pixel_values)
            loss = criterion(logits, labels)
            loss_for_step = loss / accumulation_steps

        scaler.scale(loss_for_step).backward()

        if step % accumulation_steps == 0 or step == len(dataloader):
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)

        total_loss += loss.item() * labels.size(0)
        preds = torch.argmax(logits, dim=1)
        total_correct += (preds == labels).sum().item()
        total_samples += labels.size(0)

        if step == 1 or step % log_every == 0 or step == len(dataloader):
            avg_loss = total_loss / max(1, total_samples)
            avg_acc = total_correct / max(1, total_samples)
            log(f"Treino batch {step}/{len(dataloader)} loss={avg_loss:.4f} acc={avg_acc:.4f}")

    return total_loss / max(1, total_samples), total_correct / max(1, total_samples)


@torch.no_grad()
def evaluate(model, dataloader, criterion, device, amp_enabled: bool, log_every: int):
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_samples = 0
    all_labels = []
    all_preds = []
    all_dataset_names = []

    for step, batch in enumerate(dataloader, start=1):
        pixel_values = batch["pixel_values_videos"].to(device, non_blocking=True)
        labels = batch["labels"].to(device, non_blocking=True)

        with torch.amp.autocast(device_type=device.type, enabled=amp_enabled):
            logits = model(pixel_values)
            loss = criterion(logits, labels)

        preds = torch.argmax(logits, dim=1)
        total_loss += loss.item() * labels.size(0)
        total_correct += (preds == labels).sum().item()
        total_samples += labels.size(0)
        all_labels.extend(labels.cpu().tolist())
        all_preds.extend(preds.cpu().tolist())
        all_dataset_names.extend(batch["dataset_names"])

        if step == 1 or step % log_every == 0 or step == len(dataloader):
            avg_loss = total_loss / max(1, total_samples)
            avg_acc = total_correct / max(1, total_samples)
            log(f"Validacao batch {step}/{len(dataloader)} loss={avg_loss:.4f} acc={avg_acc:.4f}")

    per_dataset = {}
    for dataset_name in sorted(set(all_dataset_names)):
        indices = [index for index, value in enumerate(all_dataset_names) if value == dataset_name]
        labels_subset = [all_labels[index] for index in indices]
        preds_subset = [all_preds[index] for index in indices]
        per_dataset[dataset_name] = {
            "accuracy": float(np.mean(np.equal(labels_subset, preds_subset))) if labels_subset else 0.0,
            "f1_queda": float(f1_score(labels_subset, preds_subset, pos_label=1, average="binary", zero_division=0)),
            "recall_queda": float(
                recall_score(labels_subset, preds_subset, pos_label=1, average="binary", zero_division=0)
            ),
            "samples": len(labels_subset),
        }

    return {
        "loss": total_loss / max(1, total_samples),
        "acc": total_correct / max(1, total_samples),
        "labels": all_labels,
        "preds": all_preds,
        "dataset_names": all_dataset_names,
        "f1_queda": float(f1_score(all_labels, all_preds, pos_label=1, average="binary", zero_division=0)),
        "recall_queda": float(
            recall_score(all_labels, all_preds, pos_label=1, average="binary", zero_division=0)
        ),
        "f1_macro": float(f1_score(all_labels, all_preds, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(all_labels, all_preds, average="macro", zero_division=0)),
        "report": classification_report(all_labels, all_preds, target_names=CLASS_NAMES, digits=4, zero_division=0),
        "confusion_matrix": confusion_matrix(all_labels, all_preds).tolist(),
        "per_dataset": per_dataset,
    }


def save_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def save_checkpoint(path: Path, state_dict: dict):
    temp_path = path.with_suffix(path.suffix + ".tmp")
    cpu_state_dict = {key: value.detach().cpu() for key, value in state_dict.items()}
    torch.save(cpu_state_dict, temp_path, _use_new_zipfile_serialization=False)
    temp_path.replace(path)


def create_output_dir(output_dir_arg: str | None) -> Path:
    if output_dir_arg:
        path = Path(output_dir_arg)
    else:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = Path("var") / "training_runs" / f"combined_{timestamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_plots(output_dir: Path, history: list[EpochMetrics], best_eval: dict):
    epochs = [item.epoch_index for item in history]
    train_loss = [item.train_loss for item in history]
    val_loss = [item.val_loss for item in history]
    train_acc = [item.train_acc for item in history]
    val_acc = [item.val_acc for item in history]
    val_f1_queda = [item.val_f1_queda for item in history]
    val_recall_queda = [item.val_recall_queda for item in history]

    plt.figure(figsize=(12, 8))
    plt.subplot(2, 1, 1)
    plt.plot(epochs, train_loss, marker="o", label="Train loss")
    plt.plot(epochs, val_loss, marker="o", label="Val loss")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.title("Perda por epoca")

    plt.subplot(2, 1, 2)
    plt.plot(epochs, train_acc, marker="o", label="Train acc")
    plt.plot(epochs, val_acc, marker="o", label="Val acc")
    plt.plot(epochs, val_f1_queda, marker="o", label="Val F1 queda")
    plt.plot(epochs, val_recall_queda, marker="o", label="Val recall queda")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.title("Metricas por epoca")
    plt.tight_layout()
    plt.savefig(output_dir / "training_curves.png", dpi=180)
    plt.close()

    matrix = np.array(best_eval["confusion_matrix"])
    plt.figure(figsize=(6, 5))
    plt.imshow(matrix, cmap="Blues")
    plt.xticks(range(len(CLASS_NAMES)), CLASS_NAMES)
    plt.yticks(range(len(CLASS_NAMES)), CLASS_NAMES)
    plt.xlabel("Predito")
    plt.ylabel("Real")
    plt.title("Matriz de confusao - melhor checkpoint")
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            plt.text(column, row, str(matrix[row, column]), ha="center", va="center", color="black")
    plt.tight_layout()
    plt.savefig(output_dir / "confusion_matrix.png", dpi=180)
    plt.close()

    dataset_names = list(best_eval["per_dataset"].keys())
    f1_values = [best_eval["per_dataset"][name]["f1_queda"] for name in dataset_names]
    recall_values = [best_eval["per_dataset"][name]["recall_queda"] for name in dataset_names]
    x = np.arange(len(dataset_names))
    width = 0.35
    plt.figure(figsize=(8, 5))
    plt.bar(x - width / 2, f1_values, width=width, label="F1 queda")
    plt.bar(x + width / 2, recall_values, width=width, label="Recall queda")
    plt.xticks(x, dataset_names)
    plt.ylim(0, 1)
    plt.legend()
    plt.grid(True, axis="y", alpha=0.3)
    plt.title("Desempenho por dataset")
    plt.tight_layout()
    plt.savefig(output_dir / "dataset_metrics.png", dpi=180)
    plt.close()


def write_report(
    output_dir: Path,
    args,
    train_summary: dict,
    val_summary: dict,
    best_epoch: int,
    best_eval: dict,
):
    lines = [
        "# Relatorio de treinamento combinado",
        "",
        "## Configuracao",
        "",
        f"- Modelo base: `{MODEL_NAME}`",
        f"- Frames por amostra: `{args.num_frames}`",
        f"- Batch size: `{args.batch_size}`",
        f"- Fase 1: `{args.phase1_epochs}` epocas",
        f"- Fase 2: `{args.phase2_epochs}` epocas",
        f"- Paciencia early stopping: `{args.patience}`",
        f"- AMP: `{'nao' if args.disable_amp else 'sim'}`",
        f"- Num workers: `{args.num_workers}`",
        "",
        "## Amostras",
        "",
        f"- Treino: `{json.dumps(train_summary, ensure_ascii=True)}`",
        f"- Validacao: `{json.dumps(val_summary, ensure_ascii=True)}`",
        "",
        "## Melhor resultado",
        "",
        f"- Melhor epoca: `{best_epoch}`",
        f"- Val acc: `{best_eval['acc']:.4f}`",
        f"- Val F1 queda: `{best_eval['f1_queda']:.4f}`",
        f"- Val recall queda: `{best_eval['recall_queda']:.4f}`",
        f"- Val F1 macro: `{best_eval['f1_macro']:.4f}`",
        "",
        "## Classification report",
        "",
        "```text",
        best_eval["report"],
        "```",
        "",
        "## Graficos gerados",
        "",
        "- `training_curves.png`",
        "- `confusion_matrix.png`",
        "- `dataset_metrics.png`",
    ]
    (output_dir / "training_report.md").write_text("\n".join(lines), encoding="utf-8")


def maybe_compile_model(model, should_compile: bool):
    if should_compile and hasattr(torch, "compile"):
        log("Compilando modelo com torch.compile().")
        return torch.compile(model)
    return model


def run_phase(
    model,
    phase_name: str,
    epochs: int,
    train_loader,
    val_loader,
    device,
    criterion,
    optimizer,
    scaler,
    args,
    output_checkpoint: Path,
    history: list[EpochMetrics],
    best_state: dict,
):
    best_metric = best_state["best_metric"]
    best_epoch = best_state["best_epoch"]
    best_eval = best_state["best_eval"]
    epochs_without_improvement = 0

    for epoch_offset in range(1, epochs + 1):
        epoch_index = best_state["global_epoch"] + 1
        best_state["global_epoch"] = epoch_index
        log(f"Iniciando {phase_name} epoca {epoch_offset}/{epochs} (global {epoch_index})")

        train_loss, train_acc = train_one_epoch(
            model=model,
            dataloader=train_loader,
            optimizer=optimizer,
            criterion=criterion,
            device=device,
            scaler=scaler,
            accumulation_steps=args.accumulation_steps,
            amp_enabled=not args.disable_amp and device.type == "cuda",
            log_every=args.log_every,
        )
        val_eval = evaluate(
            model=model,
            dataloader=val_loader,
            criterion=criterion,
            device=device,
            amp_enabled=not args.disable_amp and device.type == "cuda",
            log_every=args.log_every,
        )
        history.append(
            EpochMetrics(
                epoch_index=epoch_index,
                phase_name=phase_name,
                train_loss=train_loss,
                train_acc=train_acc,
                val_loss=val_eval["loss"],
                val_acc=val_eval["acc"],
                val_f1_queda=val_eval["f1_queda"],
                val_recall_queda=val_eval["recall_queda"],
                val_f1_macro=val_eval["f1_macro"],
                val_recall_macro=val_eval["recall_macro"],
            )
        )

        log(
            f"[Epoch {epoch_index}] train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_eval['loss']:.4f} val_acc={val_eval['acc']:.4f} "
            f"val_f1_queda={val_eval['f1_queda']:.4f} val_recall_queda={val_eval['recall_queda']:.4f}"
        )

        metric = val_eval["f1_queda"]
        if metric > best_metric:
            best_metric = metric
            best_epoch = epoch_index
            best_eval = val_eval
            save_checkpoint(output_checkpoint, model.state_dict())
            log(f"Novo melhor checkpoint salvo em: {output_checkpoint}")
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        if epochs_without_improvement >= args.patience:
            log(f"Early stopping acionado em {phase_name} na epoca global {epoch_index}.")
            break

    best_state["best_metric"] = best_metric
    best_state["best_epoch"] = best_epoch
    best_state["best_eval"] = best_eval


def main():
    args = parse_args()
    set_seed(args.seed)
    output_dir = create_output_dir(args.output_dir)
    output_checkpoint = output_dir / args.output_checkpoint
    log(f"Artefatos serao salvos em: {output_dir}")

    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
        torch.set_float32_matmul_precision("high")

    archive_samples = maybe_limit_samples(
        collect_archive_samples(Path(args.archive_root)),
        args.max_samples_per_dataset,
        args.seed,
    )
    fall_vision_samples = maybe_limit_samples(
        collect_fall_vision_samples(Path(args.fall_vision_root)),
        args.max_samples_per_dataset,
        args.seed + 1,
    )

    archive_train, archive_val = split_dataset_samples(archive_samples, args.val_size, args.seed)
    fall_train, fall_val = split_dataset_samples(fall_vision_samples, args.val_size, args.seed)
    train_samples = archive_train + fall_train
    val_samples = archive_val + fall_val
    random.Random(args.seed).shuffle(train_samples)
    random.Random(args.seed).shuffle(val_samples)

    train_summary = summarize_samples(train_samples)
    val_summary = summarize_samples(val_samples)
    log(f"Resumo treino: {train_summary}")
    log(f"Resumo validacao: {val_summary}")
    log(f"Workers: treino={args.num_workers} validacao={args.val_num_workers}")

    processor = AutoVideoProcessor.from_pretrained(MODEL_NAME, cache_dir=HF_CACHE_DIR)
    train_dataset = VideoClassificationDataset(
        train_samples,
        processor,
        args.num_frames,
        augment=True,
        max_frame_side=args.max_frame_side,
    )
    val_dataset = VideoClassificationDataset(
        val_samples,
        processor,
        args.num_frames,
        augment=False,
        max_frame_side=args.max_frame_side,
    )

    sampler = None if args.disable_sampler else create_train_sampler(train_samples)
    train_loader = build_dataloader(
        train_dataset,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        shuffle=sampler is None,
        sampler=sampler,
    )
    val_loader = build_dataloader(
        val_dataset,
        batch_size=args.batch_size,
        num_workers=args.val_num_workers,
        shuffle=False,
        sampler=None,
    )

    device = infer_device()
    log(f"Usando device: {device}")
    model = VJEPA2Classifier(MODEL_NAME, len(CLASS_NAMES), cache_dir=HF_CACHE_DIR).to(device)
    model = maybe_compile_model(model, args.compile_model)

    criterion = nn.CrossEntropyLoss(weight=compute_class_weights(train_samples, device=device))
    scaler = torch.amp.GradScaler("cuda", enabled=(not args.disable_amp and device.type == "cuda"))
    history: list[EpochMetrics] = []
    best_state = {
        "best_metric": float("-inf"),
        "best_epoch": 0,
        "best_eval": None,
        "global_epoch": 0,
    }

    freeze_backbone(model)
    optimizer = build_optimizer(model, args.head_lr, args.backbone_lr, args.weight_decay)
    run_phase(
        model=model,
        phase_name="fase_1_head",
        epochs=args.phase1_epochs,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        criterion=criterion,
        optimizer=optimizer,
        scaler=scaler,
        args=args,
        output_checkpoint=output_checkpoint,
        history=history,
        best_state=best_state,
    )

    unfreeze_backbone_tail(model, args.backbone_trainable_fraction)
    optimizer = build_optimizer(model, args.head_lr * 0.5, args.backbone_lr, args.weight_decay)
    run_phase(
        model=model,
        phase_name="fase_2_finetune",
        epochs=args.phase2_epochs,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        criterion=criterion,
        optimizer=optimizer,
        scaler=scaler,
        args=args,
        output_checkpoint=output_checkpoint,
        history=history,
        best_state=best_state,
    )

    if best_state["best_eval"] is None:
        raise RuntimeError("Nenhum checkpoint foi salvo; verifique o treino.")

    save_json(output_dir / "history.json", {"epochs": [asdict(item) for item in history]})
    save_json(
        output_dir / "split_summary.json",
        {
            "train_summary": train_summary,
            "val_summary": val_summary,
            "best_epoch": best_state["best_epoch"],
            "best_val_f1_queda": best_state["best_metric"],
            "best_eval": best_state["best_eval"],
            "args": vars(args),
        },
    )
    save_plots(output_dir, history, best_state["best_eval"])
    write_report(output_dir, args, train_summary, val_summary, best_state["best_epoch"], best_state["best_eval"])

    log(f"Treinamento concluido. Melhor epoca global: {best_state['best_epoch']}")
    log(f"Melhor val_f1_queda: {best_state['best_metric']:.4f}")
    print("\n=== Classification Report ===")
    print(best_state["best_eval"]["report"])
    print("=== Confusion Matrix ===")
    print(np.array(best_state["best_eval"]["confusion_matrix"]))


if __name__ == "__main__":
    main()
