from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


CLASS_TO_ID = {"sem_queda": 0, "queda": 1}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Valida politica final de queda com splits agrupados, threshold e smoothing temporal."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--splits", type=int, default=20)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--thresholds", default="0.56,0.6,0.65,0.7,0.75,0.8")
    parser.add_argument("--smoothing-windows", default="3,5,7")
    parser.add_argument("--min-consecutive-hits", default="1,2,3")
    parser.add_argument(
        "--alert-modes",
        default="consecutive_or_average",
        help="Lista: consecutive,average,consecutive_or_average",
    )
    parser.add_argument("--min-event-recall", type=float, default=0.95)
    parser.add_argument("--min-window-recall", type=float, default=0.85)
    parser.add_argument("--hard-negatives-manifest", default=None)
    parser.add_argument("--hard-negative-weight", type=float, default=1.0)
    parser.add_argument("--output", default="artifacts/reports/fall_production_policy_cv.json")
    parser.add_argument("--hard-negatives-output", default="artifacts/manifests/fall_cv_hard_negatives.jsonl")
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as manifest_file:
        for line in manifest_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_float_list(value: str) -> list[float]:
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def parse_int_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_str_list(value: str) -> list[str]:
    values = [item.strip() for item in value.split(",") if item.strip()]
    allowed = {"consecutive", "average", "consecutive_or_average"}
    invalid = [item for item in values if item not in allowed]
    if invalid:
        raise ValueError(f"alert-modes invalidos: {invalid}")
    return values


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


def build_model(seed: int):
    return make_pipeline(
        StandardScaler(),
        SVC(
            C=0.1,
            kernel="linear",
            class_weight="balanced",
            probability=True,
            random_state=seed,
        ),
    )


def row_key(row: dict) -> tuple[str, int, int]:
    return (row["video_path"], int(row["start_frame"]), int(row["end_frame"]))


def load_hard_negative_keys(path: str | None) -> set[tuple[str, int, int]]:
    if not path:
        return set()
    keys = set()
    with Path(path).open(encoding="utf-8") as manifest_file:
        for line in manifest_file:
            line = line.strip()
            if not line:
                continue
            keys.add(row_key(json.loads(line)))
    return keys


def sample_weights(rows: list[dict], indices: np.ndarray, hard_negative_keys: set[tuple[str, int, int]], weight: float):
    if not hard_negative_keys or weight <= 1.0:
        return None
    weights = np.ones(len(indices), dtype=np.float32)
    for local_pos, original_idx in enumerate(indices):
        row = rows[int(original_idx)]
        if row.get("label") == "sem_queda" and row_key(row) in hard_negative_keys:
            weights[local_pos] = weight
    return weights


def predict_fall_prob(model, x):
    return model.predict_proba(x)[:, CLASS_TO_ID["queda"]]


def smooth_group_predictions(
    rows,
    indices,
    probs,
    threshold: float,
    smoothing_window: int,
    min_hits: int,
    alert_mode: str,
):
    by_group = defaultdict(list)
    for local_pos, original_idx in enumerate(indices):
        row = rows[original_idx]
        by_group[row.get("group_id") or row["video_path"]].append(local_pos)
    for group_indices in by_group.values():
        group_indices.sort(
            key=lambda local_pos: (
                float(rows[indices[local_pos]].get("start_time", 0.0)),
                int(rows[indices[local_pos]].get("window_index", 0)),
            )
        )

    alerts = np.zeros(len(indices), dtype=np.int64)
    for group_indices in by_group.values():
        values = []
        consecutive = 0
        for local_pos in group_indices:
            probability = float(probs[local_pos])
            values.append(probability)
            values = values[-smoothing_window:]
            if probability >= threshold:
                consecutive += 1
            else:
                consecutive = 0
            moving_average = sum(values) / len(values)
            consecutive_alert = consecutive >= min_hits
            average_alert = len(values) == smoothing_window and moving_average >= threshold
            if alert_mode == "consecutive":
                alert = consecutive_alert
            elif alert_mode == "average":
                alert = average_alert
            else:
                alert = consecutive_alert or average_alert
            alerts[local_pos] = CLASS_TO_ID["queda"] if alert else CLASS_TO_ID["sem_queda"]
    return alerts


def event_metrics(rows, indices, y_val, preds):
    positive_groups = set()
    detected_groups = set()
    false_alert_groups = set()
    for local_pos, original_idx in enumerate(indices):
        row = rows[original_idx]
        group_id = row.get("group_id") or row["video_path"]
        if y_val[local_pos] == CLASS_TO_ID["queda"]:
            positive_groups.add(group_id)
            if preds[local_pos] == CLASS_TO_ID["queda"]:
                detected_groups.add(group_id)
        elif preds[local_pos] == CLASS_TO_ID["queda"]:
            false_alert_groups.add(group_id)
    return {
        "event_recall": 0.0 if not positive_groups else len(detected_groups) / len(positive_groups),
        "detected_groups": len(detected_groups),
        "positive_groups": len(positive_groups),
        "false_alert_groups": len(false_alert_groups),
    }


def summarize(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        key = (row["threshold"], row["smoothing_window"], row["min_consecutive_hits"], row["alert_mode"])
        grouped[key].append(row)

    summary = []
    for (threshold, smoothing_window, min_hits, alert_mode), values in grouped.items():
        summary.append(
            {
                "threshold": threshold,
                "smoothing_window": smoothing_window,
                "min_consecutive_hits": min_hits,
                "alert_mode": alert_mode,
                "splits": len(values),
                "fp_mean": float(np.mean([row["fp"] for row in values])),
                "fp_max": int(np.max([row["fp"] for row in values])),
                "fn_mean": float(np.mean([row["fn"] for row in values])),
                "fn_max": int(np.max([row["fn"] for row in values])),
                "precision_mean": float(np.mean([row["precision"] for row in values])),
                "recall_mean": float(np.mean([row["recall"] for row in values])),
                "f1_mean": float(np.mean([row["f1"] for row in values])),
                "event_recall_mean": float(np.mean([row["event_recall"] for row in values])),
                "false_alert_groups_mean": float(np.mean([row["false_alert_groups"] for row in values])),
                "false_alert_groups_max": int(np.max([row["false_alert_groups"] for row in values])),
            }
        )
    return sorted(
        summary,
        key=lambda row: (
            row["false_alert_groups_mean"],
            row["fp_mean"],
            -row["event_recall_mean"],
            -row["f1_mean"],
        ),
    )


def main():
    args = parse_args()
    rows = load_manifest(Path(args.manifest))
    features = np.load(args.features, allow_pickle=True)
    x = features["x"]
    y = features["y"]
    if len(rows) != len(x):
        raise RuntimeError(f"Manifesto/features desalinhados: rows={len(rows)} features={len(x)}")

    thresholds = parse_float_list(args.thresholds)
    smoothing_windows = parse_int_list(args.smoothing_windows)
    min_hits_values = parse_int_list(args.min_consecutive_hits)
    alert_modes = parse_str_list(args.alert_modes)
    hard_negative_keys = load_hard_negative_keys(args.hard_negatives_manifest)

    results = []
    hard_negatives = {}
    for split_id, (train_idx, val_idx) in enumerate(
        split_indices(rows, y, args.splits, args.val_size, args.seed),
        start=1,
    ):
        model = build_model(args.seed)
        weights = sample_weights(rows, train_idx, hard_negative_keys, args.hard_negative_weight)
        if weights is None:
            model.fit(x[train_idx], y[train_idx])
        else:
            model.fit(x[train_idx], y[train_idx], svc__sample_weight=weights)
        probs = predict_fall_prob(model, x[val_idx])
        y_val = y[val_idx]

        for threshold in thresholds:
            raw_preds = np.where(probs >= threshold, CLASS_TO_ID["queda"], CLASS_TO_ID["sem_queda"])
            for local_pos, original_idx in enumerate(val_idx):
                if y_val[local_pos] == CLASS_TO_ID["sem_queda"] and raw_preds[local_pos] == CLASS_TO_ID["queda"]:
                    key = (rows[original_idx]["video_path"], rows[original_idx]["start_frame"], rows[original_idx]["end_frame"])
                    item = dict(rows[original_idx])
                    item["cv_false_positive_probability"] = max(
                        float(probs[local_pos]),
                        float(hard_negatives.get(key, {}).get("cv_false_positive_probability", 0.0)),
                    )
                    item["cv_false_positive_splits"] = int(
                        hard_negatives.get(key, {}).get("cv_false_positive_splits", 0)
                    ) + 1
                    item["review_status"] = "pending"
                    hard_negatives[key] = item

            for smoothing_window in smoothing_windows:
                for min_hits in min_hits_values:
                    for alert_mode in alert_modes:
                        preds = smooth_group_predictions(
                            rows,
                            val_idx,
                            probs,
                            threshold,
                            smoothing_window,
                            min_hits,
                            alert_mode,
                        )
                        tn, fp, fn, tp = confusion_matrix(y_val, preds, labels=[0, 1]).ravel()
                        precision, recall, f1, _ = precision_recall_fscore_support(
                            y_val,
                            preds,
                            labels=[1],
                            zero_division=0,
                        )
                        event = event_metrics(rows, val_idx, y_val, preds)
                        results.append(
                            {
                                "split": split_id,
                                "threshold": threshold,
                                "smoothing_window": smoothing_window,
                                "min_consecutive_hits": min_hits,
                                "alert_mode": alert_mode,
                                "tn": int(tn),
                                "fp": int(fp),
                                "fn": int(fn),
                                "tp": int(tp),
                                "precision": float(precision[0]),
                                "recall": float(recall[0]),
                                "f1": float(f1[0]),
                                **event,
                            }
                        )
        print(f"split {split_id}/{args.splits}", flush=True)

    summary = summarize(results)
    selected_policy = next(
        (
            row
            for row in summary
            if row["event_recall_mean"] >= args.min_event_recall
            and row["recall_mean"] >= args.min_window_recall
        ),
        summary[0],
    )
    output = {
        "classifier": "svc_linear_balanced",
        "manifest": args.manifest,
        "features": args.features,
        "splits": args.splits,
        "hard_negatives_manifest": args.hard_negatives_manifest,
        "hard_negative_weight": args.hard_negative_weight,
        "selection_constraints": {
            "min_event_recall": args.min_event_recall,
            "min_window_recall": args.min_window_recall,
        },
        "summary": summary,
        "selected_policy": selected_policy,
        "all_results": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    hard_negative_rows = sorted(
        hard_negatives.values(),
        key=lambda row: (row["cv_false_positive_splits"], row["cv_false_positive_probability"]),
        reverse=True,
    )
    hard_negatives_path = Path(args.hard_negatives_output)
    hard_negatives_path.parent.mkdir(parents=True, exist_ok=True)
    with hard_negatives_path.open("w", encoding="utf-8") as output_file:
        for row in hard_negative_rows:
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(
        json.dumps(
            {
                "output": str(output_path),
                "hard_negatives": str(hard_negatives_path),
                "hard_negative_candidates": len(hard_negative_rows),
                "selected_policy": output["selected_policy"],
                "top_5": summary[:5],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
