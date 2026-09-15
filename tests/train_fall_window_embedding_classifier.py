import argparse
import json
import pickle
import random
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from transformers import AutoModel, AutoVideoProcessor

from train_fall_classifier import (
    CLASS_NAMES,
    CLASS_TO_ID,
    MODEL_NAME,
    log,
    read_video_frames_opencv,
    set_seed,
)


DEFAULT_MODEL_NAME = MODEL_NAME


def get_torch_device():
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Treina classificador de queda em janelas sobre embeddings V-JEPA 2 congelados."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--window-seconds", type=float, default=None)
    parser.add_argument("--stride-seconds", type=float, default=None)
    parser.add_argument("--subclip-seconds", type=float, default=5.0)
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cache", default="fall_window_vjepa2_embeddings.npz")
    parser.add_argument("--output", default="best_fall_window_embedding_classifier.pkl")
    parser.add_argument("--threshold-min-recall", type=float, default=0.9)
    parser.add_argument("--threshold-selection", choices=("f1", "min-fp"), default="f1")
    parser.add_argument("--max-windows", type=int, default=0)
    parser.add_argument("--local-files-only", action="store_true")
    return parser.parse_args()


def load_manifest(path: Path):
    rows = []
    with path.open(encoding="utf-8") as manifest_file:
        for line_number, line in enumerate(manifest_file, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row["_line_number"] = line_number
            rows.append(row)
    if not rows:
        raise RuntimeError(f"Manifesto vazio: {path}")
    return rows


def maybe_limit_rows(rows, max_windows: int, seed: int):
    if max_windows <= 0 or len(rows) <= max_windows:
        return list(rows)

    rng = random.Random(seed)
    by_label = {}
    for row in rows:
        by_label.setdefault(row["label"], []).append(row)

    limited = []
    labels = sorted(by_label)
    per_label = max_windows // len(labels)
    remainder = max_windows % len(labels)
    for idx, label in enumerate(labels):
        label_rows = list(by_label[label])
        rng.shuffle(label_rows)
        take = per_label + (1 if idx < remainder else 0)
        limited.extend(label_rows[:take])
    rng.shuffle(limited)
    log(f"Limitando manifesto para {len(limited)} janelas.")
    return limited


def split_rows(rows, val_size: float, seed: int):
    labels = np.array([CLASS_TO_ID[row["label"]] for row in rows], dtype=np.int64)
    groups = np.array([row.get("group_id") or row["video_path"] for row in rows])
    splitter = GroupShuffleSplit(n_splits=50, test_size=val_size, random_state=seed)
    train_idx = val_idx = None
    for candidate_train_idx, candidate_val_idx in splitter.split(rows, labels, groups):
        candidate_train_labels = set(labels[candidate_train_idx].tolist())
        candidate_val_labels = set(labels[candidate_val_idx].tolist())
        if candidate_train_labels == set(CLASS_TO_ID.values()) and candidate_val_labels == set(CLASS_TO_ID.values()):
            train_idx, val_idx = candidate_train_idx, candidate_val_idx
            break
    if train_idx is None or val_idx is None:
        raise RuntimeError(
            "Nao foi possivel criar split agrupado contendo as duas classes em treino e validacao."
        )
    train_rows = [rows[index] for index in train_idx]
    val_rows = [rows[index] for index in val_idx]

    train_groups = {row.get("group_id") or row["video_path"] for row in train_rows}
    val_groups = {row.get("group_id") or row["video_path"] for row in val_rows}
    overlap = train_groups & val_groups
    if overlap:
        raise RuntimeError(f"Vazamento de grupos entre treino/validacao: {sorted(overlap)[:5]}")

    log(f"Split agrupado: treino={len(train_rows)} validacao={len(val_rows)}")
    return train_rows, val_rows


def subclip_bounds(row, subclip_seconds: float):
    fps = float(row["fps"])
    start_frame = int(row["start_frame"])
    end_frame = int(row["end_frame"])
    subclip_frames = max(1, int(round(subclip_seconds * fps)))

    bounds = []
    current = start_frame
    while current <= end_frame:
        subclip_end = min(end_frame, current + subclip_frames - 1)
        bounds.append((current, subclip_end))
        current = subclip_end + 1
    return bounds


@torch.no_grad()
def embed_clip(model, processor, video_path: str, start_frame: int, end_frame: int, num_frames: int, device: str):
    frames = read_video_frames_opencv(
        video_path,
        num_frames=num_frames,
        start_frame=start_frame,
        end_frame=end_frame,
    )
    inputs = processor(frames, return_tensors="pt")
    pixel_values = inputs["pixel_values_videos"].to(device)
    outputs = model(pixel_values_videos=pixel_values, skip_predictor=True)
    tokens = outputs.last_hidden_state
    return torch.cat([tokens.mean(dim=1), tokens.max(dim=1).values], dim=1).squeeze(0).cpu().numpy()


def aggregate_subclip_embeddings(embeddings: list[np.ndarray]) -> np.ndarray:
    matrix = np.stack(embeddings).astype(np.float32)
    return np.concatenate(
        [
            matrix.mean(axis=0),
            matrix.max(axis=0),
            matrix.std(axis=0),
        ],
        axis=0,
    ).astype(np.float32)


@torch.no_grad()
def embed_window(model, processor, row, subclip_seconds: float, num_frames: int, device: str):
    embeddings = []
    for start_frame, end_frame in subclip_bounds(row, subclip_seconds):
        embeddings.append(
            embed_clip(
                model,
                processor,
                row["video_path"],
                start_frame,
                end_frame,
                num_frames,
                device,
            )
        )
    return aggregate_subclip_embeddings(embeddings)


def build_or_load_embeddings(args, train_rows, val_rows):
    cache_path = Path(args.cache)
    expected_metadata = {
        "manifest": str(Path(args.manifest)),
        "model_name": args.model_name,
        "subclip_seconds": args.subclip_seconds,
        "num_frames": args.num_frames,
        "seed": args.seed,
        "val_size": args.val_size,
        "max_windows": args.max_windows,
        "train_windows": len(train_rows),
        "val_windows": len(val_rows),
    }
    if cache_path.exists():
        cached = np.load(cache_path, allow_pickle=True)
        metadata = json.loads(str(cached["metadata"].item()))
        if all(metadata.get(key) == value for key, value in expected_metadata.items()):
            log(f"Embeddings carregados do cache: {cache_path}")
            return cached["x_train"], cached["y_train"], cached["x_val"], cached["y_val"]
        log("Cache existe, mas metadata nao bate com os argumentos atuais. Recalculando embeddings.")

    device = get_torch_device()
    log(f"Usando device para embeddings: {device}")
    processor = AutoVideoProcessor.from_pretrained(
        args.model_name,
        local_files_only=args.local_files_only,
    )
    model = AutoModel.from_pretrained(
        args.model_name,
        local_files_only=args.local_files_only,
    ).to(device)
    model.eval()

    def embed_many(rows, title):
        features = []
        labels = []
        for idx, row in enumerate(rows, start=1):
            features.append(embed_window(model, processor, row, args.subclip_seconds, args.num_frames, device))
            labels.append(CLASS_TO_ID[row["label"]])
            if idx == 1 or idx % 10 == 0 or idx == len(rows):
                log(f"{title}: embeddings {idx}/{len(rows)}")
        return np.stack(features), np.array(labels, dtype=np.int64)

    x_train, y_train = embed_many(train_rows, "Treino")
    x_val, y_val = embed_many(val_rows, "Validacao")
    np.savez_compressed(
        cache_path,
        x_train=x_train,
        y_train=y_train,
        x_val=x_val,
        y_val=y_val,
        metadata=json.dumps(expected_metadata),
    )
    log(f"Embeddings salvos em: {cache_path}")
    return x_train, y_train, x_val, y_val


def candidate_models(seed: int):
    return {
        "logreg_balanced": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=0.2,
                class_weight="balanced",
                max_iter=3000,
                random_state=seed,
            ),
        ),
        "svc_rbf_balanced": make_pipeline(
            StandardScaler(),
            SVC(
                C=1.0,
                gamma="scale",
                class_weight="balanced",
                probability=True,
                random_state=seed,
            ),
        ),
        "svc_linear_balanced": make_pipeline(
            StandardScaler(),
            SVC(
                C=0.1,
                kernel="linear",
                class_weight="balanced",
                probability=True,
                random_state=seed,
            ),
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=600,
            max_features="sqrt",
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed,
            n_jobs=-1,
        ),
    }


def predict_fall_prob(model, x):
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x)[:, CLASS_TO_ID["queda"]]
    scores = model.decision_function(x)
    return 1.0 / (1.0 + np.exp(-scores))


def find_threshold(y_true, fall_probs, min_recall: float, selection: str = "f1"):
    best = None
    for threshold in np.linspace(0.05, 0.95, 91):
        preds = np.where(fall_probs >= threshold, CLASS_TO_ID["queda"], CLASS_TO_ID["sem_queda"])
        report = classification_report(
            y_true,
            preds,
            labels=list(range(len(CLASS_NAMES))),
            target_names=CLASS_NAMES,
            output_dict=True,
            zero_division=0,
        )
        metrics = report["queda"]
        false_positives = int(
            np.sum((y_true == CLASS_TO_ID["sem_queda"]) & (preds == CLASS_TO_ID["queda"]))
        )
        false_negatives = int(
            np.sum((y_true == CLASS_TO_ID["queda"]) & (preds == CLASS_TO_ID["sem_queda"]))
        )
        if selection == "min-fp":
            if metrics["recall"] >= min_recall:
                score = -false_positives
                comparable = (
                    score,
                    metrics["f1-score"],
                    metrics["precision"],
                    metrics["recall"],
                    -false_negatives,
                )
            else:
                comparable = (
                    -1_000_000,
                    metrics["f1-score"],
                    metrics["precision"],
                    metrics["recall"],
                    -false_negatives,
                )
        else:
            score = metrics["f1-score"]
            if metrics["recall"] < min_recall:
                score -= 1.0
            comparable = (
                score,
                metrics["f1-score"],
                metrics["precision"],
                metrics["recall"],
                -false_positives,
            )
        candidate = (
            *comparable,
            float(threshold),
            preds,
            report,
        )
        if best is None or candidate[:5] > best[:5]:
            best = candidate
    return best


def infer_manifest_metadata(rows):
    first = rows[0]
    return {
        "window_seconds": first.get("window_seconds"),
        "stride_seconds": first.get("stride_seconds"),
        "positive_overlap_seconds": first.get("positive_overlap_seconds"),
        "manifest_mode": first.get("manifest_mode"),
        "context_before_seconds": first.get("context_before_seconds"),
        "context_after_seconds": first.get("context_after_seconds"),
        "negative_context_seconds": first.get("negative_context_seconds"),
        "negative_fall_margin_seconds": first.get("negative_fall_margin_seconds"),
        "dataset": first.get("dataset"),
    }


def main():
    args = parse_args()
    set_seed(args.seed)
    rows = maybe_limit_rows(load_manifest(Path(args.manifest)), args.max_windows, args.seed)
    train_rows, val_rows = split_rows(rows, args.val_size, args.seed)
    x_train, y_train, x_val, y_val = build_or_load_embeddings(args, train_rows, val_rows)

    log(
        "Embeddings finais: "
        f"treino={x_train.shape} classes={dict(zip(*np.unique(y_train, return_counts=True)))} | "
        f"validacao={x_val.shape} classes={dict(zip(*np.unique(y_val, return_counts=True)))}"
    )

    best_result = None
    for name, model in candidate_models(args.seed).items():
        log(f"Treinando classificador: {name}")
        model.fit(x_train, y_train)
        fall_probs = predict_fall_prob(model, x_val)
        result = find_threshold(y_val, fall_probs, args.threshold_min_recall, args.threshold_selection)
        _, f1, precision, recall, _, threshold, preds, report = result
        print(f"\n=== {name} ===")
        print(f"threshold={threshold:.2f} precision={precision:.4f} recall={recall:.4f} f1={f1:.4f}")
        print(
            classification_report(
                y_val,
                preds,
                labels=list(range(len(CLASS_NAMES))),
                target_names=CLASS_NAMES,
                digits=4,
                zero_division=0,
            )
        )
        print(confusion_matrix(y_val, preds))
        comparable = (f1, recall, precision)
        if best_result is None or comparable > best_result["comparable"]:
            best_result = {
                "name": name,
                "model": model,
                "threshold": threshold,
                "report": report,
                "confusion_matrix": confusion_matrix(y_val, preds).tolist(),
                "comparable": comparable,
            }

    manifest_metadata = infer_manifest_metadata(rows)
    payload = {
        "model": best_result["model"],
        "metadata": {
            "model_type": "vjepa2_window_embedding_sklearn",
            "classifier": best_result["name"],
            "backbone": args.model_name,
            "num_frames": args.num_frames,
            "subclip_seconds": args.subclip_seconds,
            "window_seconds": args.window_seconds or manifest_metadata["window_seconds"],
            "stride_seconds": args.stride_seconds or manifest_metadata["stride_seconds"],
            "positive_overlap_seconds": manifest_metadata["positive_overlap_seconds"],
            "manifest_mode": manifest_metadata["manifest_mode"],
            "context_before_seconds": manifest_metadata["context_before_seconds"],
            "context_after_seconds": manifest_metadata["context_after_seconds"],
            "negative_context_seconds": manifest_metadata["negative_context_seconds"],
            "negative_fall_margin_seconds": manifest_metadata["negative_fall_margin_seconds"],
            "class_names": CLASS_NAMES,
            "threshold": best_result["threshold"],
            "threshold_selection": args.threshold_selection,
            "metrics": best_result["report"]["queda"],
            "confusion_matrix": best_result["confusion_matrix"],
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "manifest": str(Path(args.manifest)),
            "cache": args.cache,
            "dataset": manifest_metadata["dataset"],
            "train_windows": len(train_rows),
            "val_windows": len(val_rows),
        },
    }

    output_path = Path(args.output)
    with output_path.open("wb") as output_file:
        pickle.dump(payload, output_file)
    metadata_path = output_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(payload["metadata"], indent=2), encoding="utf-8")
    log(f"Melhor classificador salvo em: {output_path}")
    log(f"Metadata salva em: {metadata_path}")


if __name__ == "__main__":
    main()
