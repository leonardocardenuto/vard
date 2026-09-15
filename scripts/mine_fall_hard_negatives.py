from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

import numpy as np


CLASS_TO_ID = {"sem_queda": 0, "queda": 1}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Minera janelas sem queda que o modelo acha suspeitas para retreino com hard negatives."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--checkpoint", default="fall_detection/models/vard_fall_window_production.pkl")
    parser.add_argument("--min-probability", type=float, default=0.35)
    parser.add_argument("--output", default="artifacts/manifests/fall_hard_negatives.jsonl")
    parser.add_argument("--report", default="artifacts/reports/fall_hard_negatives_report.json")
    parser.add_argument("--limit", type=int, default=0)
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as manifest_file:
        for line in manifest_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def predict_fall_prob(classifier, features: np.ndarray) -> np.ndarray:
    if hasattr(classifier, "predict_proba"):
        return classifier.predict_proba(features)[:, CLASS_TO_ID["queda"]]
    scores = classifier.decision_function(features)
    return 1.0 / (1.0 + np.exp(-scores))


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
    probs = predict_fall_prob(payload["model"], x)

    candidates = []
    for index, (row, label, probability) in enumerate(zip(rows, y, probs)):
        if label != CLASS_TO_ID["sem_queda"]:
            continue
        if probability < args.min_probability:
            continue
        item = dict(row)
        item["hard_negative_probability"] = float(probability)
        item["hard_negative_source_index"] = index
        item["review_status"] = "pending"
        candidates.append(item)

    candidates.sort(key=lambda row: row["hard_negative_probability"], reverse=True)
    if args.limit > 0:
        candidates = candidates[: args.limit]

    output_path = Path(args.output)
    report_path = Path(args.report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for row in candidates:
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    by_group = {}
    for row in candidates:
        group_id = row.get("group_id") or row["video_path"]
        by_group[group_id] = by_group.get(group_id, 0) + 1

    report = {
        "checkpoint": str(args.checkpoint),
        "manifest": str(args.manifest),
        "features": str(args.features),
        "min_probability": args.min_probability,
        "candidates": len(candidates),
        "groups": len(by_group),
        "top_groups": sorted(by_group.items(), key=lambda item: item[1], reverse=True)[:20],
        "top_candidates": candidates[:20],
        "next_step": "Revisar manualmente janelas pending; confirmadas entram como sem_queda no proximo treino.",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "report": str(report_path), "candidates": len(candidates)}, indent=2))


if __name__ == "__main__":
    main()
