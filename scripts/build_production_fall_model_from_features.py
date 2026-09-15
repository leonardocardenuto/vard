from __future__ import annotations

import argparse
import json
import pickle
import time
from pathlib import Path

import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


CLASS_NAMES = ["sem_queda", "queda"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Treina o classificador final de producao a partir do cache de embeddings ja validado."
    )
    parser.add_argument(
        "--features",
        default="fall_window_vjepa2_mcfd_annotation_context_2s_3s_clean_full_embeddings.npz",
    )
    parser.add_argument("--manifest", default="fall_windows_mcfd_annotation_context_2s_3s_clean.jsonl")
    parser.add_argument("--output", default="fall_detection/models/vard_fall_window_production.pkl")
    parser.add_argument("--threshold", type=float, default=0.56)
    parser.add_argument("--policy-report", default=None)
    parser.add_argument("--policy-threshold", type=float, default=None)
    parser.add_argument("--policy-smoothing-window", type=int, default=None)
    parser.add_argument("--policy-min-consecutive-hits", type=int, default=None)
    parser.add_argument("--policy-alert-mode", default=None)
    parser.add_argument("--hard-negatives-manifest", default=None)
    parser.add_argument("--hard-negative-weight", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_first_manifest_row(path: Path) -> dict:
    with path.open(encoding="utf-8") as manifest_file:
        for line in manifest_file:
            line = line.strip()
            if line:
                return json.loads(line)
    raise RuntimeError(f"Manifesto vazio: {path}")


def load_feature_metadata(features) -> dict:
    if "metadata" not in features:
        return {}
    try:
        return json.loads(str(features["metadata"].item()))
    except Exception:
        return {}


def infer_auxiliary_metadata(feature_metadata: dict) -> dict:
    metadata = {}
    primary_path = feature_metadata.get("primary")
    if primary_path and Path(primary_path).exists():
        primary_features = np.load(primary_path, allow_pickle=True)
        metadata.update(infer_auxiliary_metadata(load_feature_metadata(primary_features)))

    auxiliary_path = feature_metadata.get("auxiliary")
    if not auxiliary_path and feature_metadata.get("base_features"):
        base_path = Path(feature_metadata["base_features"])
        if base_path.exists():
            base_features = np.load(base_path, allow_pickle=True)
            metadata.update(infer_auxiliary_metadata(load_feature_metadata(base_features)))
            return metadata
    if not auxiliary_path:
        return metadata
    path = Path(auxiliary_path)
    if not path.exists():
        return metadata
    aux = np.load(path, allow_pickle=True)
    aux_metadata = load_feature_metadata(aux)
    if aux_metadata.get("feature_type") == "yolo_pose_window_stats":
        metadata.update(
            {
                "auxiliary_pose_model": aux_metadata.get("pose_model"),
                "auxiliary_pose_frames_per_window": aux_metadata.get("frames_per_window", 6),
                "auxiliary_pose_confidence": aux_metadata.get("confidence", 0.15),
                "auxiliary_pose_feature_dimensions": aux_metadata.get("feature_dimensions"),
            }
        )
        return metadata
    yolo_model = aux_metadata.get("yolo_model")
    if not yolo_model:
        return metadata
    metadata.update(
        {
            "auxiliary_feature_type": "yolo_obb_window_stats",
            "auxiliary_yolo_model": yolo_model,
            "auxiliary_yolo_frames_per_window": aux_metadata.get("frames_per_window", 4),
            "auxiliary_yolo_confidence": aux_metadata.get("confidence", 0.15),
            "auxiliary_yolo_class_filter": aux_metadata.get("class_filter"),
            "auxiliary_feature_version": aux_metadata.get("feature_version", "legacy_v1"),
            "auxiliary_feature_dimensions": aux_metadata.get(
                "feature_dimensions", feature_metadata.get("auxiliary_shape", [None, 0])[1]
            ),
        }
    )
    return metadata


def row_key(row: dict) -> tuple[str, int, int]:
    return (row["video_path"], int(row["start_frame"]), int(row["end_frame"]))


def load_manifest_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as manifest_file:
        for line in manifest_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise RuntimeError(f"Manifesto vazio: {path}")
    return rows


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


def sample_weights(rows: list[dict], hard_negative_keys: set[tuple[str, int, int]], weight: float):
    if not hard_negative_keys or weight <= 1.0:
        return None
    weights = np.ones(len(rows), dtype=np.float32)
    for index, row in enumerate(rows):
        if row.get("label") == "sem_queda" and row_key(row) in hard_negative_keys:
            weights[index] = weight
    return weights


def main():
    args = parse_args()
    features_path = Path(args.features)
    manifest_path = Path(args.manifest)
    output_path = Path(args.output)

    features = np.load(features_path, allow_pickle=True)
    x = features["x"]
    y = features["y"]
    feature_metadata = load_feature_metadata(features)
    auxiliary_metadata = infer_auxiliary_metadata(feature_metadata)
    rows = load_manifest_rows(manifest_path)
    first = rows[0]
    selected_policy = None
    if args.policy_report:
        policy_report = json.loads(Path(args.policy_report).read_text(encoding="utf-8"))
        selected_policy = policy_report["selected_policy"]
        if (
            args.policy_threshold is not None
            or args.policy_smoothing_window is not None
            or args.policy_min_consecutive_hits is not None
        ):
            for row in policy_report["summary"]:
                if args.policy_threshold is not None and float(row["threshold"]) != float(args.policy_threshold):
                    continue
                if args.policy_smoothing_window is not None and int(row["smoothing_window"]) != args.policy_smoothing_window:
                    continue
                if (
                    args.policy_min_consecutive_hits is not None
                    and int(row["min_consecutive_hits"]) != args.policy_min_consecutive_hits
                ):
                    continue
                if args.policy_alert_mode is not None and row.get("alert_mode") != args.policy_alert_mode:
                    continue
                selected_policy = row
                break
            else:
                raise RuntimeError("Politica solicitada nao encontrada no policy report.")
        args.threshold = float(selected_policy["threshold"])

    model = make_pipeline(
        StandardScaler(),
        SVC(
            C=0.1,
            kernel="linear",
            class_weight="balanced",
            probability=True,
            random_state=args.seed,
        ),
    )
    hard_negative_keys = load_hard_negative_keys(args.hard_negatives_manifest)
    weights = sample_weights(rows, hard_negative_keys, args.hard_negative_weight)
    if weights is None:
        model.fit(x, y)
    else:
        model.fit(x, y, svc__sample_weight=weights)

    threshold_selection = "fixed_from_group_cv_policy"
    if selected_policy:
        threshold_selection = (
            "fixed_from_group_cv_zero_false_alert_policy"
            if float(selected_policy.get("fp_mean", 0.0)) == 0.0
            else "fixed_from_group_cv_low_false_alert_policy"
        )

    metadata = {
        "model_type": "vjepa2_window_embedding_sklearn",
        "classifier": "svc_linear_balanced",
        "backbone": "facebook/vjepa2-vitl-fpc64-256",
        "num_frames": 16,
        "subclip_seconds": 5.0,
        "window_seconds": None,
        "stride_seconds": None,
        "positive_overlap_seconds": first.get("positive_overlap_seconds"),
        "manifest_mode": first.get("manifest_mode"),
        "context_before_seconds": first.get("context_before_seconds"),
        "context_after_seconds": first.get("context_after_seconds"),
        "negative_context_seconds": first.get("negative_context_seconds"),
        "negative_fall_margin_seconds": first.get("negative_fall_margin_seconds"),
        "class_names": CLASS_NAMES,
        "threshold": args.threshold,
        "threshold_selection": threshold_selection,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "manifest": str(manifest_path),
        "cache": str(features_path),
        "hard_negatives_manifest": args.hard_negatives_manifest,
        "hard_negative_weight": args.hard_negative_weight,
        "hard_negative_count": len(hard_negative_keys),
        "dataset": first.get("dataset"),
        "train_windows": int(len(y)),
        "artifact_role": "production",
        "production_window_seconds": 5.0,
        "production_stride_seconds": 1.0,
        "production_sample_fps": 6.0,
        "production_smoothing_window": int(selected_policy["smoothing_window"]) if selected_policy else 5,
        "production_min_consecutive_hits": int(selected_policy["min_consecutive_hits"]) if selected_policy else 2,
        "production_alert_mode": selected_policy.get("alert_mode", "consecutive_or_average")
        if selected_policy
        else "consecutive_or_average",
        "production_alert_cooldown_seconds": 60.0,
        "validation_protocol": (
            "20 grouped splits; selected conservative temporal policy by false-alert groups first"
            if selected_policy
            else "20 grouped splits; selected lowest mean FP with mean recall >= 0.90"
        ),
        "cv_summary": {
            "classifier": "svc_linear_balanced",
            "threshold": args.threshold,
            "fp_mean": selected_policy["fp_mean"] if selected_policy else 4.85,
            "fp_max": selected_policy["fp_max"] if selected_policy else 23,
            "fn_mean": selected_policy["fn_mean"] if selected_policy else 5.7,
            "fn_max": selected_policy["fn_max"] if selected_policy else 15,
            "precision_mean": selected_policy["precision_mean"] if selected_policy else 0.9185,
            "recall_mean": selected_policy["recall_mean"] if selected_policy else 0.9007,
            "f1_mean": selected_policy["f1_mean"] if selected_policy else 0.9062,
            "event_recall_mean": selected_policy.get("event_recall_mean") if selected_policy else None,
            "false_alert_groups_mean": selected_policy.get("false_alert_groups_mean") if selected_policy else None,
            "false_alert_groups_max": selected_policy.get("false_alert_groups_max") if selected_policy else None,
            "smoothing_window": selected_policy.get("smoothing_window") if selected_policy else None,
            "min_consecutive_hits": selected_policy.get("min_consecutive_hits") if selected_policy else None,
            "alert_mode": selected_policy.get("alert_mode") if selected_policy else None,
        },
        "serving_notes": (
            "Use recent frames over production_window_seconds, split into subclips, "
            "aggregate V-JEPA2 embeddings with mean/max/std, then apply threshold."
        ),
        **auxiliary_metadata,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output_file:
        pickle.dump({"model": model, "metadata": metadata}, output_file)
    output_path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Modelo de producao salvo em: {output_path}")
    print(f"Metadata salva em: {output_path.with_suffix('.json')}")


if __name__ == "__main__":
    main()
