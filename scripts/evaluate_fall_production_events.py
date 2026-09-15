from __future__ import annotations

import argparse
import json
import pickle
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, confusion_matrix


CLASS_NAMES = ["sem_queda", "queda"]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Avalia o modelo de producao em metricas por janela, evento e alerta temporal."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--features", required=True, help=".npz com x/y alinhados ao manifesto.")
    parser.add_argument("--checkpoint", default="fall_detection/models/vard_fall_window_production.pkl")
    parser.add_argument("--output", default="artifacts/reports/fall_production_eval.json")
    parser.add_argument("--thresholds", default=None, help="Lista separada por virgula. Ex: 0.56,0.65,0.75")
    parser.add_argument("--smoothing-windows", default="3,5,7")
    parser.add_argument("--min-consecutive-hits", default="1,2,3")
    parser.add_argument("--alert-modes", default=None)
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as manifest_file:
        for line in manifest_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise RuntimeError(f"Manifesto vazio: {path}")
    return rows


def parse_float_list(value: str | None, default: list[float]) -> list[float]:
    if not value:
        return default
    return [float(item.strip()) for item in value.split(",") if item.strip()]


def parse_int_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def parse_str_list(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    values = [item.strip() for item in value.split(",") if item.strip()]
    allowed = {"consecutive", "average", "consecutive_or_average"}
    invalid = [item for item in values if item not in allowed]
    if invalid:
        raise ValueError(f"alert-modes invalidos: {invalid}")
    return values


def predict_fall_prob(classifier, features: np.ndarray) -> np.ndarray:
    if hasattr(classifier, "predict_proba"):
        return classifier.predict_proba(features)[:, CLASS_TO_ID["queda"]]
    scores = classifier.decision_function(features)
    return 1.0 / (1.0 + np.exp(-scores))


def window_metrics(rows: list[dict], y_true: np.ndarray, probs: np.ndarray, threshold: float) -> dict:
    preds = np.where(probs >= threshold, CLASS_TO_ID["queda"], CLASS_TO_ID["sem_queda"])
    report = classification_report(
        y_true,
        preds,
        labels=list(range(len(CLASS_NAMES))),
        target_names=CLASS_NAMES,
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(y_true, preds, labels=list(range(len(CLASS_NAMES)))).tolist()
    negative_seconds = sum(
        max(0.0, float(row["end_time"]) - float(row["start_time"]))
        for row, label in zip(rows, y_true)
        if label == CLASS_TO_ID["sem_queda"]
    )
    false_positives = int(
        np.sum((y_true == CLASS_TO_ID["sem_queda"]) & (preds == CLASS_TO_ID["queda"]))
    )
    false_negatives = int(
        np.sum((y_true == CLASS_TO_ID["queda"]) & (preds == CLASS_TO_ID["sem_queda"]))
    )
    fp_per_hour = 0.0 if negative_seconds <= 0 else false_positives / (negative_seconds / 3600.0)
    return {
        "threshold": threshold,
        "classification_report": report,
        "confusion_matrix": matrix,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "negative_window_hours": negative_seconds / 3600.0,
        "false_positives_per_negative_window_hour": fp_per_hour,
    }


def event_recall(rows: list[dict], y_true: np.ndarray, probs: np.ndarray, threshold: float) -> dict:
    groups_with_fall = set()
    detected_groups = set()
    detection_latencies = []
    for row, label, probability in zip(rows, y_true, probs):
        group_id = row.get("group_id") or row["video_path"]
        if label != CLASS_TO_ID["queda"]:
            continue
        groups_with_fall.add(group_id)
        if probability >= threshold:
            detected_groups.add(group_id)
            annotation_start = row.get("annotation_start_frame")
            fps = float(row.get("fps") or 0.0)
            if annotation_start is not None and fps > 0:
                event_start_time = float(annotation_start) / fps
                detection_latencies.append(max(0.0, float(row["start_time"]) - event_start_time))

    total = len(groups_with_fall)
    detected = len(detected_groups)
    return {
        "event_recall_by_group": 0.0 if total == 0 else detected / total,
        "detected_groups": detected,
        "total_positive_groups": total,
        "latency_seconds_mean": None if not detection_latencies else float(np.mean(detection_latencies)),
        "latency_seconds_max": None if not detection_latencies else float(np.max(detection_latencies)),
    }


def temporal_grid(
    rows: list[dict],
    y_true: np.ndarray,
    probs: np.ndarray,
    thresholds: list[float],
    smoothing_windows: list[int],
    min_hits_values: list[int],
    alert_modes: list[str],
) -> list[dict]:
    by_group = defaultdict(list)
    for index, row in enumerate(rows):
        by_group[row.get("group_id") or row["video_path"]].append(index)
    for group_rows in by_group.values():
        group_rows.sort(key=lambda idx: (float(rows[idx].get("start_time", 0.0)), int(rows[idx].get("window_index", 0))))

    results = []
    for threshold in thresholds:
        for smoothing_window in smoothing_windows:
            for min_hits in min_hits_values:
                for alert_mode in alert_modes:
                    false_alerts = 0
                    positive_groups = set()
                    detected_groups = set()
                    alert_windows = 0
                    for group_id, indices in by_group.items():
                        values = []
                        consecutive = 0
                        group_alerted_negative = False
                        for idx in indices:
                            probability = float(probs[idx])
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
                            if alert:
                                alert_windows += 1
                                if y_true[idx] == CLASS_TO_ID["queda"]:
                                    detected_groups.add(group_id)
                                elif not group_alerted_negative:
                                    false_alerts += 1
                                    group_alerted_negative = True
                            if y_true[idx] == CLASS_TO_ID["queda"]:
                                positive_groups.add(group_id)

                    recall = 0.0 if not positive_groups else len(detected_groups) / len(positive_groups)
                    results.append(
                        {
                            "threshold": threshold,
                            "smoothing_window": smoothing_window,
                            "min_consecutive_hits": min_hits,
                            "alert_mode": alert_mode,
                            "event_recall_by_group": recall,
                            "detected_groups": len(detected_groups),
                            "total_positive_groups": len(positive_groups),
                            "false_alert_groups": false_alerts,
                            "alert_windows": alert_windows,
                        }
                    )
    return sorted(
        results,
        key=lambda row: (
            row["false_alert_groups"],
            -row["event_recall_by_group"],
            row["alert_windows"],
        ),
    )


def top_errors(rows: list[dict], y_true: np.ndarray, probs: np.ndarray, threshold: float) -> dict:
    false_positives = []
    false_negatives = []
    for index, (row, label, probability) in enumerate(zip(rows, y_true, probs)):
        pred = CLASS_TO_ID["queda"] if probability >= threshold else CLASS_TO_ID["sem_queda"]
        item = {
            "index": index,
            "group_id": row.get("group_id"),
            "video_path": row.get("video_path"),
            "start_time": row.get("start_time"),
            "end_time": row.get("end_time"),
            "label": row.get("label"),
            "fall_probability": float(probability),
        }
        if label == CLASS_TO_ID["sem_queda"] and pred == CLASS_TO_ID["queda"]:
            false_positives.append(item)
        if label == CLASS_TO_ID["queda"] and pred == CLASS_TO_ID["sem_queda"]:
            false_negatives.append(item)

    false_positives.sort(key=lambda item: item["fall_probability"], reverse=True)
    false_negatives.sort(key=lambda item: item["fall_probability"])
    return {
        "top_false_positives": false_positives[:20],
        "top_false_negatives": false_negatives[:20],
    }


def main():
    args = parse_args()
    rows = load_manifest(Path(args.manifest))
    features = np.load(args.features, allow_pickle=True)
    x = features["x"]
    y = features["y"]
    if len(rows) != len(x):
        raise RuntimeError(f"Manifesto/features desalinhados: rows={len(rows)} features={len(x)}")

    with Path(args.checkpoint).open("rb") as checkpoint_file:
        payload = pickle.load(checkpoint_file)
    metadata = payload.get("metadata", {})
    classifier = payload["model"]
    threshold = float(metadata.get("threshold") or 0.5)
    thresholds = parse_float_list(args.thresholds, [threshold, 0.6, 0.65, 0.7, 0.75, 0.8])
    smoothing_windows = parse_int_list(args.smoothing_windows)
    min_hits_values = parse_int_list(args.min_consecutive_hits)
    alert_modes = parse_str_list(
        args.alert_modes,
        [metadata.get("production_alert_mode", "consecutive_or_average")],
    )
    probs = predict_fall_prob(classifier, x)

    output = {
        "checkpoint": str(args.checkpoint),
        "manifest": str(args.manifest),
        "features": str(args.features),
        "metadata": metadata,
        "window_metrics": window_metrics(rows, y, probs, threshold),
        "event_metrics": event_recall(rows, y, probs, threshold),
        "temporal_grid": temporal_grid(rows, y, probs, thresholds, smoothing_windows, min_hits_values, alert_modes),
        "errors": top_errors(rows, y, probs, threshold),
        "notes": [
            "Metricas em manifesto annotation-context sao sanidade no conjunto completo, nao substituem CV agrupado.",
            "false_positives_per_negative_window_hour usa duracao somada das janelas negativas, nao horas reais continuas.",
        ],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print(json.dumps({
        "output": str(output_path),
        "window_queda": output["window_metrics"]["classification_report"]["queda"],
        "confusion_matrix": output["window_metrics"]["confusion_matrix"],
        "event_metrics": output["event_metrics"],
        "best_temporal": output["temporal_grid"][:5],
    }, indent=2))


if __name__ == "__main__":
    main()
