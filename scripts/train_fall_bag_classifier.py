from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import precision_recall_fscore_support
from sklearn.model_selection import GroupShuffleSplit

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fall_detection.person_masked_bag import PersonMaskedBagClassifier


CLASS_NAMES = ["sem_queda", "queda"]
CLASS_TO_ID = {"sem_queda": 0, "queda": 1}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Treina classificador PyTorch de queda por conjunto de janelas sobre features person-masked V-JEPA + pose."
    )
    parser.add_argument("--features", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="artifacts/models/experimental/vard_fall_person_masked_bag.pt")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--splits", type=int, default=20)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--hidden-dim", type=int, default=256)
    parser.add_argument("--hidden-layers", type=int, default=1)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--loss", choices=("ce", "focal"), default="ce")
    parser.add_argument("--focal-gamma", type=float, default=2.0)
    parser.add_argument("--label-smoothing", type=float, default=0.0)
    parser.add_argument("--hard-negatives-manifest", default=None)
    parser.add_argument("--hard-negative-weight", type=float, default=1.0)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--device", default=None)
    parser.add_argument("--production-window-seconds", type=float, default=None)
    parser.add_argument("--production-stride-seconds", type=float, default=1.0)
    parser.add_argument("--production-smoothing-window", type=int, default=1)
    parser.add_argument("--production-min-consecutive-hits", type=int, default=1)
    parser.add_argument(
        "--production-alert-mode",
        choices=("consecutive", "average", "consecutive_or_average"),
        default="consecutive",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as jsonl_file:
        for line in jsonl_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise RuntimeError(f"Manifesto vazio: {path}")
    return rows


def load_feature_metadata(features) -> dict:
    if "metadata" not in features:
        return {}
    try:
        return json.loads(str(features["metadata"].item()))
    except Exception:
        return {}


def standardize(train_x: np.ndarray, target_x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = train_x.mean(axis=0).astype(np.float32)
    std = train_x.std(axis=0).astype(np.float32)
    std = np.where(std < 1e-6, 1.0, std).astype(np.float32)
    return ((target_x - mean) / std).astype(np.float32), mean, std


def class_weights(y: np.ndarray, device) -> torch.Tensor:
    counts = np.bincount(y, minlength=len(CLASS_NAMES)).astype(np.float32)
    weights = counts.sum() / np.maximum(counts, 1.0)
    weights = weights / weights.mean()
    return torch.tensor(weights, dtype=torch.float32, device=device)


def row_key(row: dict) -> tuple[str, int, int]:
    return (row["video_path"], int(row["start_frame"]), int(row["end_frame"]))


def load_hard_negative_keys(path: str | None) -> set[tuple[str, int, int]]:
    if not path:
        return set()
    keys = set()
    with Path(path).open(encoding="utf-8") as manifest_file:
        for line in manifest_file:
            line = line.strip()
            if line:
                keys.add(row_key(json.loads(line)))
    return keys


def sample_weights_for_rows(
    rows: list[dict],
    indices: np.ndarray,
    hard_negative_keys: set[tuple[str, int, int]],
    hard_negative_weight: float,
) -> np.ndarray:
    weights = np.ones(len(indices), dtype=np.float32)
    if not hard_negative_keys or hard_negative_weight <= 1.0:
        return weights
    for local_pos, original_idx in enumerate(indices):
        row = rows[int(original_idx)]
        if row.get("label") == "sem_queda" and row_key(row) in hard_negative_keys:
            weights[local_pos] = float(hard_negative_weight)
    return weights


def classification_loss(logits, labels, class_weight, sample_weight, args):
    ce = nn.functional.cross_entropy(
        logits,
        labels,
        weight=class_weight,
        label_smoothing=args.label_smoothing,
        reduction="none",
    )
    if args.loss == "focal":
        pt = torch.exp(-ce).clamp(1e-6, 1.0)
        ce = ((1.0 - pt) ** args.focal_gamma) * ce
    return (ce * sample_weight).mean()


def train_model(
    train_x: np.ndarray,
    train_y: np.ndarray,
    args,
    device,
    sample_weights: np.ndarray | None = None,
) -> PersonMaskedBagClassifier:
    model = PersonMaskedBagClassifier(
        input_dim=train_x.shape[1],
        hidden_dim=args.hidden_dim,
        dropout=args.dropout,
        num_classes=len(CLASS_NAMES),
        hidden_layers=args.hidden_layers,
    ).to(device)
    if sample_weights is None:
        sample_weights = np.ones(len(train_y), dtype=np.float32)
    dataset = TensorDataset(
        torch.tensor(train_x, dtype=torch.float32),
        torch.tensor(train_y, dtype=torch.long),
        torch.tensor(sample_weights, dtype=torch.float32),
    )
    generator = torch.Generator()
    generator.manual_seed(args.seed)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True, generator=generator)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    weight = class_weights(train_y, device)

    model.train()
    for _ in range(args.epochs):
        for batch_x, batch_y, batch_weight in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            batch_weight = batch_weight.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = classification_loss(model(batch_x), batch_y, weight, batch_weight, args)
            loss.backward()
            optimizer.step()
    model.eval()
    return model


@torch.no_grad()
def predict_fall_prob(model: PersonMaskedBagClassifier, x: np.ndarray, device) -> np.ndarray:
    logits = model(torch.tensor(x, dtype=torch.float32, device=device))
    return torch.softmax(logits, dim=1)[:, CLASS_TO_ID["queda"]].detach().cpu().numpy()


def temperature_adjust(probs: np.ndarray, temperature: float) -> np.ndarray:
    probs = np.clip(probs.astype(np.float64), 1e-6, 1.0 - 1e-6)
    logits = np.log(probs / (1.0 - probs))
    adjusted = 1.0 / (1.0 + np.exp(-logits / max(1e-6, temperature)))
    return adjusted.astype(np.float32)


def split_indices(rows: list[dict], y: np.ndarray, splits: int, val_size: float, seed: int):
    groups = np.array([row.get("group_id") or row.get("video_path") or str(index) for index, row in enumerate(rows)])
    splitter = GroupShuffleSplit(n_splits=max(splits * 5, splits), test_size=val_size, random_state=seed)
    yielded = 0
    for train_idx, val_idx in splitter.split(rows, y, groups):
        if set(y[train_idx].tolist()) != set(CLASS_TO_ID.values()):
            continue
        if set(y[val_idx].tolist()) != set(CLASS_TO_ID.values()):
            continue
        yield train_idx, val_idx
        yielded += 1
        if yielded >= splits:
            break


def cv_summary(rows: list[dict], x: np.ndarray, y: np.ndarray, args) -> dict:
    if args.splits <= 0:
        return {"splits": 0, "warning": "CV desabilitada por --splits <= 0."}

    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    split_rows = []
    hard_negative_keys = load_hard_negative_keys(args.hard_negatives_manifest)
    try:
        split_iterator = split_indices(rows, y, args.splits, args.val_size, args.seed)
        enumerated_splits = enumerate(split_iterator, start=1)
        for split_id, (train_idx, val_idx) in enumerated_splits:
            train_x = x[train_idx]
            val_x, mean, std = standardize(train_x, x[val_idx])
            train_x = ((train_x - mean) / std).astype(np.float32)
            weights = sample_weights_for_rows(rows, train_idx, hard_negative_keys, args.hard_negative_weight)
            model = train_model(train_x, y[train_idx], args, device, sample_weights=weights)
            probs = predict_fall_prob(model, val_x, device)
            probs = temperature_adjust(probs, args.temperature)
            preds = (probs >= args.threshold).astype(np.int64)
            precision, recall, f1, _ = precision_recall_fscore_support(
                y[val_idx],
                preds,
                labels=[CLASS_TO_ID["sem_queda"], CLASS_TO_ID["queda"]],
                zero_division=0,
            )
            false_positives = int(((preds == CLASS_TO_ID["queda"]) & (y[val_idx] == CLASS_TO_ID["sem_queda"])).sum())
            false_negatives = int(((preds == CLASS_TO_ID["sem_queda"]) & (y[val_idx] == CLASS_TO_ID["queda"])).sum())
            split_rows.append(
                {
                    "split": split_id,
                    "fp": false_positives,
                    "fn": false_negatives,
                    "precision_queda": float(precision[CLASS_TO_ID["queda"]]),
                    "recall_queda": float(recall[CLASS_TO_ID["queda"]]),
                    "f1_queda": float(f1[CLASS_TO_ID["queda"]]),
                }
            )
    except ValueError as exc:
        return {"splits": 0, "warning": f"CV agrupada indisponivel: {exc}"}

    if not split_rows:
        return {"splits": 0, "warning": "Nao houve splits agrupados validos com as duas classes."}

    return {
        "splits": len(split_rows),
        "threshold": args.threshold,
        "fp_mean": float(np.mean([row["fp"] for row in split_rows])),
        "fp_max": int(np.max([row["fp"] for row in split_rows])),
        "fn_mean": float(np.mean([row["fn"] for row in split_rows])),
        "fn_max": int(np.max([row["fn"] for row in split_rows])),
        "precision_mean": float(np.mean([row["precision_queda"] for row in split_rows])),
        "recall_mean": float(np.mean([row["recall_queda"] for row in split_rows])),
        "f1_mean": float(np.mean([row["f1_queda"] for row in split_rows])),
        "details": split_rows,
    }


def main():
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    features_path = Path(args.features)
    manifest_path = Path(args.manifest)
    output_path = Path(args.output)

    features = np.load(features_path, allow_pickle=True)
    x = features["x"].astype(np.float32)
    y = features["y"].astype(np.int64)
    rows = load_jsonl(manifest_path)
    if len(rows) != len(x):
        raise RuntimeError(f"Manifesto/features desalinhados: rows={len(rows)} features={len(x)}")

    feature_metadata = load_feature_metadata(features)
    summary = cv_summary(rows, x, y, args)
    train_x, feature_mean, feature_std = standardize(x, x)
    hard_negative_keys = load_hard_negative_keys(args.hard_negatives_manifest)
    all_indices = np.arange(len(rows))
    weights = sample_weights_for_rows(rows, all_indices, hard_negative_keys, args.hard_negative_weight)
    model = train_model(train_x, y, args, device, sample_weights=weights)

    production_window_seconds = (
        args.production_window_seconds
        if args.production_window_seconds is not None
        else float(feature_metadata.get("bag_window_seconds") or 5.0)
    )
    metadata = {
        **feature_metadata,
        "model_type": "person_masked_vjepa_pose_bag_pt",
        "artifact_format": "torch_pt",
        "classifier": "person_masked_bag_mlp",
        "input_dim": int(x.shape[1]),
        "hidden_dim": args.hidden_dim,
        "hidden_layers": args.hidden_layers,
        "dropout": args.dropout,
        "loss": args.loss,
        "focal_gamma": args.focal_gamma,
        "label_smoothing": args.label_smoothing,
        "temperature": max(1e-6, float(args.temperature)),
        "class_names": CLASS_NAMES,
        "threshold": args.threshold,
        "threshold_selection": "fixed_user_threshold",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "manifest": str(manifest_path),
        "cache": str(features_path),
        "train_bags": int(len(y)),
        "hard_negatives_manifest": args.hard_negatives_manifest,
        "hard_negative_weight": args.hard_negative_weight,
        "hard_negative_count": len(hard_negative_keys),
        "artifact_role": "experimental",
        "production_window_seconds": production_window_seconds,
        "production_stride_seconds": args.production_stride_seconds,
        "production_min_window_seconds": float(feature_metadata.get("min_window_seconds") or 0.75),
        "production_sample_fps": float(feature_metadata.get("sample_fps") or 6.0),
        "production_smoothing_window": args.production_smoothing_window,
        "production_min_consecutive_hits": args.production_min_consecutive_hits,
        "production_alert_mode": args.production_alert_mode,
        "cv_summary": summary,
        "serving_notes": (
            "Read recent frames, split into bag windows, mask person with YOLO-seg, "
            "extract frozen V-JEPA embeddings plus YOLO pose and mask stats, aggregate bag, classify."
        ),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "metadata": metadata,
            "state_dict": model.state_dict(),
            "feature_mean": torch.tensor(feature_mean.astype(np.float32)),
            "feature_std": torch.tensor(feature_std.astype(np.float32)),
        },
        output_path,
    )
    output_path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "cv_summary": summary}, indent=2), flush=True)


if __name__ == "__main__":
    main()
