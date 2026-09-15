from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import precision_recall_fscore_support

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.train_fall_bag_classifier import (
    CLASS_TO_ID,
    load_jsonl,
    predict_fall_prob,
    row_key,
    split_indices,
    standardize,
    train_model,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Avalia thresholds/politica temporal para o classificador person-masked bag e minera hard negatives."
    )
    parser.add_argument("--features", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="artifacts/reports/fall_bag_policy_cv.json")
    parser.add_argument("--hard-negatives-output", default="artifacts/manifests/fall_bag_hard_negatives.jsonl")
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
    parser.add_argument("--thresholds", default="0.5,0.6,0.7,0.8,0.9,0.95,0.97,0.99")
    parser.add_argument("--smoothing-windows", default="1,2,3")
    parser.add_argument("--min-consecutive-hits", default="1,2")
    parser.add_argument("--alert-modes", default="consecutive,average,consecutive_or_average")
    parser.add_argument("--min-recall", type=float, default=0.80)
    parser.add_argument("--temperature-grid", default="1,1.5,2,3,5,8,12")
    parser.add_argument("--hard-negative-threshold", type=float, default=None)
    parser.add_argument("--device", default=None)
    return parser.parse_args()


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


def group_indices(rows: list[dict], indices: np.ndarray) -> dict[str, list[int]]:
    grouped = defaultdict(list)
    for local_pos, original_idx in enumerate(indices):
        row = rows[int(original_idx)]
        grouped[row.get("group_id") or row["video_path"]].append(local_pos)
    for values in grouped.values():
        values.sort(
            key=lambda local_pos: (
                float(rows[int(indices[local_pos])].get("start_time", 0.0)),
                int(rows[int(indices[local_pos])].get("window_index", 0)),
            )
        )
    return grouped


def apply_policy(
    rows: list[dict],
    indices: np.ndarray,
    probs: np.ndarray,
    threshold: float,
    smoothing_window: int,
    min_hits: int,
    alert_mode: str,
) -> np.ndarray:
    if smoothing_window <= 1 and min_hits <= 1 and alert_mode == "consecutive":
        return (probs >= threshold).astype(np.int64)

    preds = np.zeros(len(indices), dtype=np.int64)
    for positions in group_indices(rows, indices).values():
        values = []
        consecutive = 0
        for local_pos in positions:
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
            preds[local_pos] = CLASS_TO_ID["queda"] if alert else CLASS_TO_ID["sem_queda"]
    return preds


def event_metrics(rows: list[dict], indices: np.ndarray, y_true: np.ndarray, preds: np.ndarray) -> dict:
    positive_groups = set()
    detected_groups = set()
    false_alert_groups = set()
    for local_pos, original_idx in enumerate(indices):
        row = rows[int(original_idx)]
        group_id = row.get("group_id") or row["video_path"]
        if y_true[local_pos] == CLASS_TO_ID["queda"]:
            positive_groups.add(group_id)
            if preds[local_pos] == CLASS_TO_ID["queda"]:
                detected_groups.add(group_id)
        elif preds[local_pos] == CLASS_TO_ID["queda"]:
            false_alert_groups.add(group_id)
    return {
        "event_recall": 0.0 if not positive_groups else len(detected_groups) / len(positive_groups),
        "positive_groups": len(positive_groups),
        "detected_groups": len(detected_groups),
        "false_alert_groups": len(false_alert_groups),
    }


def summarize_policy(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        key = (row["temperature"], row["threshold"], row["smoothing_window"], row["min_consecutive_hits"], row["alert_mode"])
        grouped[key].append(row)
    summary = []
    for (temperature, threshold, smoothing_window, min_hits, alert_mode), values in grouped.items():
        summary.append(
            {
                "temperature": temperature,
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
            -row["recall_mean"],
            -row["f1_mean"],
        ),
    )


def collect_oof_predictions(rows, x, y, args):
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    split_payloads = []
    all_probs = np.zeros(len(y), dtype=np.float32)
    all_seen = np.zeros(len(y), dtype=bool)
    for split_id, (train_idx, val_idx) in enumerate(split_indices(rows, y, args.splits, args.val_size, args.seed), start=1):
        train_x = x[train_idx]
        val_x, mean, std = standardize(train_x, x[val_idx])
        train_x = ((train_x - mean) / std).astype(np.float32)
        model = train_model(train_x, y[train_idx], args, device)
        probs = predict_fall_prob(model, val_x, device)
        split_payloads.append({"split": split_id, "indices": val_idx, "probs": probs, "y": y[val_idx]})
        all_probs[val_idx] = probs
        all_seen[val_idx] = True
        print(f"CV bag policy split {split_id}/{args.splits}", flush=True)
    return split_payloads, all_probs, all_seen


def temperature_adjust(probs: np.ndarray, temperature: float) -> np.ndarray:
    probs = np.clip(probs.astype(np.float64), 1e-6, 1.0 - 1e-6)
    logits = np.log(probs / (1.0 - probs))
    adjusted = 1.0 / (1.0 + np.exp(-logits / max(1e-6, temperature)))
    return adjusted.astype(np.float32)


def main():
    args = parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    rows = load_jsonl(Path(args.manifest))
    features = np.load(args.features, allow_pickle=True)
    x = features["x"].astype(np.float32)
    y = features["y"].astype(np.int64)
    if len(rows) != len(x):
        raise RuntimeError(f"Manifesto/features desalinhados: rows={len(rows)} features={len(x)}")

    thresholds = parse_float_list(args.thresholds)
    temperatures = parse_float_list(args.temperature_grid)
    smoothing_windows = parse_int_list(args.smoothing_windows)
    min_hits_values = parse_int_list(args.min_consecutive_hits)
    alert_modes = parse_str_list(args.alert_modes)

    split_payloads, all_probs, all_seen = collect_oof_predictions(rows, x, y, args)
    policy_rows = []
    hard_negative_candidates = {}
    for temperature in temperatures:
        for payload in split_payloads:
            indices = payload["indices"]
            y_val = payload["y"]
            probs = temperature_adjust(payload["probs"], temperature)
            for threshold in thresholds:
                raw_preds = (probs >= threshold).astype(np.int64)
                for local_pos, original_idx in enumerate(indices):
                    if y_val[local_pos] == CLASS_TO_ID["sem_queda"] and raw_preds[local_pos] == CLASS_TO_ID["queda"]:
                        row = dict(rows[int(original_idx)])
                        key = row_key(row)
                        previous = hard_negative_candidates.get(key)
                        if previous is None or float(probs[local_pos]) > previous["cv_false_positive_probability"]:
                            row["cv_false_positive_probability"] = float(probs[local_pos])
                            row["cv_false_positive_threshold"] = float(threshold)
                            row["cv_false_positive_temperature"] = float(temperature)
                            row["cv_false_positive_split"] = int(payload["split"])
                            hard_negative_candidates[key] = row

                for smoothing_window in smoothing_windows:
                    for min_hits in min_hits_values:
                        for alert_mode in alert_modes:
                            preds = apply_policy(
                                rows,
                                indices,
                                probs,
                                threshold,
                                smoothing_window,
                                min_hits,
                                alert_mode,
                            )
                            precision, recall, f1, _ = precision_recall_fscore_support(
                                y_val,
                                preds,
                                labels=[CLASS_TO_ID["sem_queda"], CLASS_TO_ID["queda"]],
                                zero_division=0,
                            )
                            events = event_metrics(rows, indices, y_val, preds)
                            policy_rows.append(
                                {
                                    "split": int(payload["split"]),
                                    "temperature": float(temperature),
                                    "threshold": float(threshold),
                                    "smoothing_window": int(smoothing_window),
                                    "min_consecutive_hits": int(min_hits),
                                    "alert_mode": alert_mode,
                                    "fp": int(((preds == CLASS_TO_ID["queda"]) & (y_val == CLASS_TO_ID["sem_queda"])).sum()),
                                    "fn": int(((preds == CLASS_TO_ID["sem_queda"]) & (y_val == CLASS_TO_ID["queda"])).sum()),
                                    "precision": float(precision[CLASS_TO_ID["queda"]]),
                                    "recall": float(recall[CLASS_TO_ID["queda"]]),
                                    "f1": float(f1[CLASS_TO_ID["queda"]]),
                                    **events,
                                }
                            )

    summary = summarize_policy(policy_rows)
    eligible = [row for row in summary if row["recall_mean"] >= args.min_recall]
    selected_policy = eligible[0] if eligible else summary[0]
    hard_negative_threshold = (
        args.hard_negative_threshold
        if args.hard_negative_threshold is not None
        else float(selected_policy["threshold"])
    )
    hard_negative_rows = [
        row
        for row in hard_negative_candidates.values()
        if float(row["cv_false_positive_probability"]) >= hard_negative_threshold
    ]
    hard_negative_rows.sort(key=lambda row: row["cv_false_positive_probability"], reverse=True)

    output = {
        "features": args.features,
        "manifest": args.manifest,
        "splits": args.splits,
        "min_recall": args.min_recall,
        "selected_policy": selected_policy,
        "summary": summary,
        "hard_negatives_output": args.hard_negatives_output,
        "hard_negative_candidates": len(hard_negative_rows),
        "oof_coverage": int(all_seen.sum()),
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    hard_negatives_path = Path(args.hard_negatives_output)
    hard_negatives_path.parent.mkdir(parents=True, exist_ok=True)
    with hard_negatives_path.open("w", encoding="utf-8") as hard_file:
        for row in hard_negative_rows:
            hard_file.write(json.dumps(row) + "\n")

    print(json.dumps({"selected_policy": selected_policy, "hard_negative_candidates": len(hard_negative_rows)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
