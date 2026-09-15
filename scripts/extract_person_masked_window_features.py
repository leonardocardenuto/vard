from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoVideoProcessor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fall_detection.person_masked_bag import (
    PersonSegmenter,
    extract_bag_feature_from_frames,
    load_jsonl,
    read_video_segment_frames,
)


CLASS_TO_ID = {"sem_queda": 0, "queda": 1}
DEFAULT_JEPA_BACKBONE = "facebook/vjepa2-vitl-fpc64-256"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai features de queda por bag: YOLO-seg pessoa + YOLO pose + V-JEPA congelado."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--jepa-backbone", default=DEFAULT_JEPA_BACKBONE)
    parser.add_argument("--person-seg-model", default="yolo11n-seg.pt")
    parser.add_argument("--person-seg-confidence", type=float, default=0.25)
    parser.add_argument("--background-mode", choices=("mask_black",), default="mask_black")
    parser.add_argument("--no-person-policy", choices=("original", "zero"), default="zero")
    parser.add_argument("--no-original-jepa", action="store_true")
    parser.add_argument("--pose-model", default="yolo11n-pose.pt")
    parser.add_argument("--pose-confidence", type=float, default=0.15)
    parser.add_argument("--pose-frames-per-window", type=int, default=6)
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--sample-fps", type=float, default=6.0)
    parser.add_argument("--bag-window-seconds", type=float, default=5.0)
    parser.add_argument("--bag-stride-seconds", type=float, default=1.0)
    parser.add_argument("--min-window-seconds", type=float, default=0.75)
    parser.add_argument("--top-k-windows", type=int, default=3)
    parser.add_argument("--device", default=None)
    parser.add_argument("--max-rows", type=int, default=0)
    return parser.parse_args()


def row_label_id(row: dict) -> int:
    if "label_id" in row:
        return int(row["label_id"])
    label = row.get("label")
    if label not in CLASS_TO_ID:
        raise RuntimeError(f"Label invalido ou ausente: {label!r}")
    return CLASS_TO_ID[label]


def main():
    args = parse_args()
    rows = load_jsonl(args.manifest)
    if args.max_rows > 0:
        rows = rows[: args.max_rows]

    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    processor = AutoVideoProcessor.from_pretrained(args.jepa_backbone)
    jepa_model = AutoModel.from_pretrained(args.jepa_backbone).to(device)
    jepa_model.eval()

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Instale ultralytics: pip install -r requirements-ml.txt") from exc

    segmenter = PersonSegmenter(
        model_path=args.person_seg_model,
        confidence=args.person_seg_confidence,
        background_mode=args.background_mode,
        no_person_policy=args.no_person_policy,
        device=args.device,
    )
    pose_model = YOLO(args.pose_model)

    features = []
    labels = []
    window_counts = []
    feature_info = {}
    for index, row in enumerate(rows, start=1):
        frames = read_video_segment_frames(
            row["video_path"],
            sample_fps=args.sample_fps,
            start_frame=row.get("start_frame"),
            end_frame=row.get("end_frame"),
        )
        feature, info = extract_bag_feature_from_frames(
            frames,
            sample_fps=args.sample_fps,
            bag_window_seconds=args.bag_window_seconds,
            bag_stride_seconds=args.bag_stride_seconds,
            min_window_seconds=args.min_window_seconds,
            num_frames=args.num_frames,
            processor=processor,
            jepa_model=jepa_model,
            device=device,
            segmenter=segmenter,
            pose_model=pose_model,
            pose_frames_per_window=args.pose_frames_per_window,
            pose_confidence=args.pose_confidence,
            top_k=args.top_k_windows,
            include_original_jepa=not args.no_original_jepa,
        )
        features.append(feature.squeeze(0))
        labels.append(row_label_id(row))
        window_counts.append(info["bag_window_count"])
        feature_info = info
        if index == 1 or index % 10 == 0 or index == len(rows):
            print(
                f"person-masked bag features {index}/{len(rows)} "
                f"windows={info['bag_window_count']} dims={info['bag_feature_dimensions']}",
                flush=True,
            )

    metadata = {
        "feature_type": "dual_view_person_masked_vjepa_pose_bag"
        if not args.no_original_jepa
        else "person_masked_vjepa_pose_bag",
        "model_type": "person_masked_vjepa_pose_bag_pt",
        "manifest": args.manifest,
        "jepa_backbone": args.jepa_backbone,
        "person_seg_model": args.person_seg_model,
        "person_seg_confidence": args.person_seg_confidence,
        "background_mode": args.background_mode,
        "no_person_policy": args.no_person_policy,
        "include_original_jepa": not args.no_original_jepa,
        "pose_model": args.pose_model,
        "pose_confidence": args.pose_confidence,
        "pose_frames_per_window": args.pose_frames_per_window,
        "num_frames": args.num_frames,
        "sample_fps": args.sample_fps,
        "bag_window_seconds": args.bag_window_seconds,
        "bag_stride_seconds": args.bag_stride_seconds,
        "min_window_seconds": args.min_window_seconds,
        "top_k_windows": args.top_k_windows,
        "window_feature_dimensions": feature_info.get("window_feature_dimensions"),
        "bag_feature_dimensions": feature_info.get("bag_feature_dimensions"),
        "bag_window_counts": {
            "min": int(np.min(window_counts)),
            "max": int(np.max(window_counts)),
            "mean": float(np.mean(window_counts)),
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        x=np.stack(features).astype(np.float32),
        y=np.array(labels, dtype=np.int64),
        metadata=json.dumps(metadata),
    )
    print(json.dumps(metadata, indent=2), flush=True)
    print(f"Features salvas em: {output_path}", flush=True)


if __name__ == "__main__":
    main()
