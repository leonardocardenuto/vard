import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import GroupShuffleSplit

from train_fall_classifier import CLASS_NAMES, CLASS_TO_ID, log
from train_fall_window_embedding_classifier import (
    candidate_models,
    find_threshold,
    load_manifest,
    predict_fall_prob,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Roda validacao cruzada agrupada sobre embeddings de janelas ja extraidos."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--features", required=True, help=".npz com arrays x e y alinhados ao manifesto.")
    parser.add_argument("--splits", type=int, default=20)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threshold-min-recall", type=float, default=0.95)
    parser.add_argument("--threshold-selection", choices=("f1", "min-fp"), default="min-fp")
    return parser.parse_args()


def split_indices(rows, y, splits: int, val_size: float, seed: int):
    groups = np.array([row.get("group_id") or row["video_path"] for row in rows])
    splitter = GroupShuffleSplit(n_splits=splits * 5, test_size=val_size, random_state=seed)
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


def summarize(results):
    by_model = {}
    for result in results:
        by_model.setdefault(result["classifier"], []).append(result)

    summary = []
    for classifier, rows in by_model.items():
        summary.append(
            {
                "classifier": classifier,
                "splits": len(rows),
                "fp_mean": float(np.mean([row["fp"] for row in rows])),
                "fp_max": int(np.max([row["fp"] for row in rows])),
                "fn_mean": float(np.mean([row["fn"] for row in rows])),
                "fn_max": int(np.max([row["fn"] for row in rows])),
                "precision_mean": float(np.mean([row["precision"] for row in rows])),
                "recall_mean": float(np.mean([row["recall"] for row in rows])),
                "f1_mean": float(np.mean([row["f1"] for row in rows])),
                "threshold_mean": float(np.mean([row["threshold"] for row in rows])),
            }
        )
    return sorted(summary, key=lambda row: (row["fp_mean"], row["fn_mean"], -row["f1_mean"]))


def main():
    args = parse_args()
    rows = load_manifest(Path(args.manifest))
    features = np.load(args.features, allow_pickle=True)
    x = features["x"]
    y = features["y"]
    if len(rows) != len(x):
        raise RuntimeError(f"Manifesto e features desalinhados: rows={len(rows)} x={len(x)}")

    results = []
    split_count = 0
    for split_id, (train_idx, val_idx) in enumerate(
        split_indices(rows, y, args.splits, args.val_size, args.seed),
        start=1,
    ):
        split_count += 1
        x_train, y_train = x[train_idx], y[train_idx]
        x_val, y_val = x[val_idx], y[val_idx]

        for name, model in candidate_models(args.seed).items():
            model.fit(x_train, y_train)
            fall_probs = predict_fall_prob(model, x_val)
            result = find_threshold(
                y_val,
                fall_probs,
                args.threshold_min_recall,
                args.threshold_selection,
            )
            _, f1, precision, recall, _, threshold, preds, _ = result
            tn, fp, fn, tp = confusion_matrix(
                y_val,
                preds,
                labels=list(range(len(CLASS_NAMES))),
            ).ravel()
            results.append(
                {
                    "split": split_id,
                    "classifier": name,
                    "threshold": float(threshold),
                    "precision": float(precision),
                    "recall": float(recall),
                    "f1": float(f1),
                    "tn": int(tn),
                    "fp": int(fp),
                    "fn": int(fn),
                    "tp": int(tp),
                }
            )

        log(f"Split {split_id}/{args.splits} concluido.")

    if split_count == 0:
        raise RuntimeError("Nenhum split valido com as duas classes em treino e validacao.")

    print("\n=== Cross-validation summary ===")
    for row in summarize(results):
        print(json.dumps(row, sort_keys=True))


if __name__ == "__main__":
    main()
