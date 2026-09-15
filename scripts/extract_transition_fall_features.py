from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from transformers import AutoModel, AutoVideoProcessor

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fall_detection.person_masked_bag import (
    PersonSegmenter,
    embed_masked_window,
    extract_pose_window_features,
    load_jsonl,
    mask_window_frames,
    read_video_segment_frames,
)


CLASS_TO_ID = {"sem_queda": 0, "queda": 1}
DEFAULT_JEPA_BACKBONE = "facebook/vjepa2-vitl-fpc64-256"
PHASES = ("pre", "motion", "post")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai features de transicao pre/motion/post para queda, usando original + YOLO-seg + pose."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--jepa-backbone", default=DEFAULT_JEPA_BACKBONE)
    parser.add_argument("--person-seg-model", default="yolo11n-seg.pt")
    parser.add_argument("--person-seg-confidence", type=float, default=0.25)
    parser.add_argument("--pose-model", default="yolo11n-pose.pt")
    parser.add_argument("--pose-confidence", type=float, default=0.15)
    parser.add_argument("--pose-frames-per-phase", type=int, default=4)
    parser.add_argument("--num-frames", type=int, default=8)
    parser.add_argument("--sample-fps", type=float, default=6.0)
    parser.add_argument("--pre-seconds", type=float, default=2.0)
    parser.add_argument("--motion-seconds", type=float, default=1.0)
    parser.add_argument("--post-seconds", type=float, default=2.0)
    parser.add_argument("--device", default=None)
    parser.add_argument("--max-rows", type=int, default=0)
    return parser.parse_args()


def read_video_metadata(video_path: str) -> tuple[int, float]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir video: {video_path}")
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    cap.release()
    if frame_count <= 0 or fps <= 0:
        raise RuntimeError(f"Video invalido: {video_path}")
    return frame_count, fps


def clamp_bounds(start: int, end: int, min_frame: int, max_frame: int) -> tuple[int, int]:
    start = max(min_frame, min(max_frame, int(start)))
    end = max(min_frame, min(max_frame, int(end)))
    if end < start:
        end = start
    return start, end


def transition_phase_bounds(row: dict, args) -> dict[str, tuple[int, int]]:
    frame_count, fps = read_video_metadata(row["video_path"])
    video_min = 0
    video_max = frame_count - 1
    start = int(row["start_frame"])
    end = int(row["end_frame"])
    label = row.get("label")

    if label == "queda" and row.get("annotation_start_frame") is not None and row.get("annotation_end_frame") is not None:
        ann_start = int(row["annotation_start_frame"])
        ann_end = int(row["annotation_end_frame"])
        center = (ann_start + ann_end) // 2
        motion_half = max(1, int(round(args.motion_seconds * fps / 2.0)))
        motion_start, motion_end = clamp_bounds(center - motion_half, center + motion_half, video_min, video_max)
        pre_frames = max(1, int(round(args.pre_seconds * fps)))
        post_frames = max(1, int(round(args.post_seconds * fps)))
        pre_start, pre_end = clamp_bounds(motion_start - pre_frames, motion_start - 1, video_min, video_max)
        post_start, post_end = clamp_bounds(motion_end + 1, motion_end + post_frames, video_min, video_max)
        return {"pre": (pre_start, pre_end), "motion": (motion_start, motion_end), "post": (post_start, post_end)}

    # For hard negatives, force the same temporal structure over the available clip.
    total = max(3, end - start + 1)
    first_end = start + max(1, total // 3) - 1
    second_end = start + max(2, (2 * total) // 3) - 1
    return {
        "pre": clamp_bounds(start, first_end, video_min, video_max),
        "motion": clamp_bounds(first_end + 1, second_end, video_min, video_max),
        "post": clamp_bounds(second_end + 1, end, video_min, video_max),
    }


def row_label_id(row: dict) -> int:
    if "label_id" in row:
        return int(row["label_id"])
    return CLASS_TO_ID[row["label"]]


def phase_feature(
    frames: list[np.ndarray],
    *,
    processor,
    jepa_model,
    device,
    segmenter,
    pose_model,
    args,
) -> np.ndarray:
    masked_frames, mask_features = mask_window_frames(segmenter, frames)
    original_jepa = embed_masked_window(jepa_model, processor, frames, args.num_frames, device)
    masked_jepa = embed_masked_window(jepa_model, processor, masked_frames, args.num_frames, device)
    pose_features = extract_pose_window_features(
        pose_model,
        frames,
        frames_per_window=args.pose_frames_per_phase,
        confidence=args.pose_confidence,
        device=str(device) if device is not None else None,
    )
    return np.concatenate([original_jepa, masked_jepa, pose_features, mask_features]).astype(np.float32)


def build_transition_feature(phase_features: dict[str, np.ndarray]) -> np.ndarray:
    pre = phase_features["pre"]
    motion = phase_features["motion"]
    post = phase_features["post"]
    return np.concatenate(
        [
            pre,
            motion,
            post,
            motion - pre,
            post - motion,
            post - pre,
            np.maximum.reduce([pre, motion, post]),
            np.stack([pre, motion, post]).std(axis=0),
        ]
    ).astype(np.float32)


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
        background_mode="mask_black",
        no_person_policy="zero",
        device=args.device,
    )
    pose_model = YOLO(args.pose_model)

    features = []
    labels = []
    phase_bounds_rows = []
    for index, row in enumerate(rows, start=1):
        bounds = transition_phase_bounds(row, args)
        phase_features = {}
        for phase in PHASES:
            start_frame, end_frame = bounds[phase]
            frames = read_video_segment_frames(
                row["video_path"],
                sample_fps=args.sample_fps,
                start_frame=start_frame,
                end_frame=end_frame,
            )
            phase_features[phase] = phase_feature(
                frames,
                processor=processor,
                jepa_model=jepa_model,
                device=device,
                segmenter=segmenter,
                pose_model=pose_model,
                args=args,
            )
        features.append(build_transition_feature(phase_features))
        labels.append(row_label_id(row))
        phase_bounds_rows.append({phase: list(bounds[phase]) for phase in PHASES})
        if index == 1 or index % 10 == 0 or index == len(rows):
            print(f"transition features {index}/{len(rows)} dims={len(features[-1])}", flush=True)

    metadata = {
        "feature_type": "pre_motion_post_dual_view_transition",
        "model_type": "person_masked_vjepa_pose_bag_pt",
        "manifest": args.manifest,
        "jepa_backbone": args.jepa_backbone,
        "person_seg_model": args.person_seg_model,
        "person_seg_confidence": args.person_seg_confidence,
        "background_mode": "mask_black",
        "no_person_policy": "zero",
        "include_original_jepa": True,
        "transition_phases": list(PHASES),
        "pre_seconds": args.pre_seconds,
        "motion_seconds": args.motion_seconds,
        "post_seconds": args.post_seconds,
        "pose_model": args.pose_model,
        "pose_confidence": args.pose_confidence,
        "pose_frames_per_phase": args.pose_frames_per_phase,
        "num_frames": args.num_frames,
        "sample_fps": args.sample_fps,
        "phase_feature_dimensions": int(len(phase_features["pre"])),
        "transition_feature_dimensions": int(len(features[0]) if features else 0),
        "phase_bounds_sample": phase_bounds_rows[:5],
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
