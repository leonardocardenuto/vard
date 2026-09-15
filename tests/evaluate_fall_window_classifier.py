import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import classification_report, confusion_matrix
from transformers import AutoModel, AutoVideoProcessor

from train_fall_classifier import CLASS_NAMES, CLASS_TO_ID, MODEL_NAME, log
from train_fall_window_embedding_classifier import embed_window


DEFAULT_MODEL_NAME = MODEL_NAME


def get_torch_device():
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Avalia um classificador de queda treinado em janelas temporais."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--checkpoint", default="best_fall_window_embedding_classifier.pkl")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--cache", default=None)
    parser.add_argument("--max-windows", type=int, default=0)
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def load_manifest(path: Path):
    rows = []
    with path.open(encoding="utf-8") as manifest_file:
        for line in manifest_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise RuntimeError(f"Manifesto vazio: {path}")
    return rows


def predict_fall_prob(classifier, features):
    if hasattr(classifier, "predict_proba"):
        return classifier.predict_proba(features)[:, CLASS_TO_ID["queda"]]
    scores = classifier.decision_function(features)
    return 1.0 / (1.0 + np.exp(-scores))


@torch.no_grad()
def build_or_load_features(rows, metadata, cache_path: str | None, local_files_only: bool = False):
    if cache_path:
        path = Path(cache_path)
        if path.exists():
            cached = np.load(path, allow_pickle=True)
            log(f"Features de avaliacao carregadas do cache: {path}")
            return cached["x"], cached["y"]

    model_name = metadata.get("backbone") or DEFAULT_MODEL_NAME
    num_frames = int(metadata.get("num_frames") or 16)
    subclip_seconds = float(metadata.get("subclip_seconds") or 5.0)

    device = get_torch_device()
    log(f"Usando device para avaliacao: {device}")
    processor = AutoVideoProcessor.from_pretrained(model_name, local_files_only=local_files_only)
    model = AutoModel.from_pretrained(model_name, local_files_only=local_files_only).to(device)
    model.eval()

    features = []
    labels = []
    for idx, row in enumerate(rows, start=1):
        features.append(embed_window(model, processor, row, subclip_seconds, num_frames, device))
        labels.append(CLASS_TO_ID[row["label"]])
        if idx == 1 or idx % 10 == 0 or idx == len(rows):
            log(f"Avaliacao: embeddings {idx}/{len(rows)}")

    x = np.stack(features)
    y = np.array(labels, dtype=np.int64)
    if cache_path:
        np.savez_compressed(cache_path, x=x, y=y)
        log(f"Features de avaliacao salvas em: {cache_path}")
    return x, y


def false_positives_per_minute(rows, y_true, preds):
    false_positive_seconds = 0.0
    false_positives = 0
    for row, true_label, pred_label in zip(rows, y_true, preds):
        if true_label == CLASS_TO_ID["sem_queda"]:
            false_positive_seconds += max(0.0, float(row["end_time"]) - float(row["start_time"]))
            if pred_label == CLASS_TO_ID["queda"]:
                false_positives += 1
    if false_positive_seconds <= 0:
        return 0.0
    return false_positives / (false_positive_seconds / 60.0)


def event_level_recall_by_group(rows, y_true, preds):
    positive_groups = {}
    detected_groups = set()
    for row, true_label, pred_label in zip(rows, y_true, preds):
        group_id = row.get("group_id") or row["video_path"]
        if true_label == CLASS_TO_ID["queda"]:
            positive_groups[group_id] = True
            if pred_label == CLASS_TO_ID["queda"]:
                detected_groups.add(group_id)
    if not positive_groups:
        return 0.0, 0, 0
    return len(detected_groups) / len(positive_groups), len(detected_groups), len(positive_groups)


def main():
    args = parse_args()
    rows = load_manifest(Path(args.manifest))
    if args.max_windows > 0:
        rows = rows[: args.max_windows]
        log(f"Limitando avaliacao para {len(rows)} janelas.")

    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint nao encontrado: {checkpoint_path}")

    with checkpoint_path.open("rb") as checkpoint_file:
        payload = pickle.load(checkpoint_file)
    classifier = payload["model"]
    metadata = payload.get("metadata", {})
    if metadata.get("model_type") != "vjepa2_window_embedding_sklearn":
        log(f"Aviso: model_type inesperado: {metadata.get('model_type')}")

    threshold = args.threshold if args.threshold is not None else float(metadata.get("threshold") or 0.5)
    x, y_true = build_or_load_features(rows, metadata, args.cache, args.local_files_only)
    fall_probs = predict_fall_prob(classifier, x)
    preds = np.where(fall_probs >= threshold, CLASS_TO_ID["queda"], CLASS_TO_ID["sem_queda"])

    print("\n=== Window Classification Report ===")
    print(f"threshold={threshold:.4f}")
    print(
        classification_report(
            y_true,
            preds,
            labels=list(range(len(CLASS_NAMES))),
            target_names=CLASS_NAMES,
            digits=4,
            zero_division=0,
        )
    )
    print("=== Confusion Matrix ===")
    print(confusion_matrix(y_true, preds))

    fp_per_minute = false_positives_per_minute(rows, y_true, preds)
    event_recall, detected, total = event_level_recall_by_group(rows, y_true, preds)
    print("\n=== Temporal Metrics ===")
    print(f"false_positives_per_minute: {fp_per_minute:.4f}")
    print(f"event_level_recall_by_group: {event_recall:.4f} ({detected}/{total})")


if __name__ == "__main__":
    main()
