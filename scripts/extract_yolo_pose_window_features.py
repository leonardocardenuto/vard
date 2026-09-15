from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


CLASS_TO_ID = {"sem_queda": 0, "queda": 1}
COCO_KEYPOINTS = 17


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai features temporais YOLO Pose por janela para auxiliar o classificador de queda."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pose-model", default="yolo11n-pose.pt")
    parser.add_argument("--frames-per-window", type=int, default=6)
    parser.add_argument("--confidence", type=float, default=0.15)
    parser.add_argument("--device", default=None)
    parser.add_argument("--max-windows", type=int, default=0)
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


def sample_frame_indices(start_frame: int, end_frame: int, count: int) -> list[int]:
    if count <= 1:
        return [start_frame]
    return np.linspace(start_frame, end_frame, count).astype(int).tolist()


def read_frame(video_path: str, frame_index: int):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir video: {video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame_bgr = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Nao foi possivel ler frame {frame_index}: {video_path}")
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def empty_pose_feature() -> np.ndarray:
    return np.zeros(COCO_KEYPOINTS * 3 + 18, dtype=np.float32)


def best_person_keypoints(result, image_shape) -> np.ndarray:
    height, width = image_shape[:2]
    if getattr(result, "keypoints", None) is None or result.keypoints is None:
        return empty_pose_feature()
    if result.keypoints.xy is None or len(result.keypoints.xy) == 0:
        return empty_pose_feature()

    xy = result.keypoints.xy.detach().cpu().numpy()
    conf = result.keypoints.conf.detach().cpu().numpy() if result.keypoints.conf is not None else np.ones(xy.shape[:2])
    if xy.shape[0] == 0:
        return empty_pose_feature()

    scores = conf.mean(axis=1)
    person_index = int(np.argmax(scores))
    points = xy[person_index]
    point_conf = conf[person_index]
    norm = np.array([max(float(width), 1.0), max(float(height), 1.0)], dtype=np.float32)
    norm_points = points / norm

    visible = point_conf > 0.2
    if visible.any():
        valid_points = norm_points[visible]
        min_xy = valid_points.min(axis=0)
        max_xy = valid_points.max(axis=0)
        center = valid_points.mean(axis=0)
        span = np.maximum(max_xy - min_xy, 1e-6)
    else:
        min_xy = max_xy = center = span = np.zeros(2, dtype=np.float32)

    def kp(index: int) -> np.ndarray:
        if index >= len(norm_points) or point_conf[index] <= 0.2:
            return np.array([np.nan, np.nan], dtype=np.float32)
        return norm_points[index].astype(np.float32)

    left_shoulder, right_shoulder = kp(5), kp(6)
    left_hip, right_hip = kp(11), kp(12)
    left_ankle, right_ankle = kp(15), kp(16)
    nose = kp(0)

    shoulders = np.nanmean(np.stack([left_shoulder, right_shoulder]), axis=0)
    hips = np.nanmean(np.stack([left_hip, right_hip]), axis=0)
    ankles = np.nanmean(np.stack([left_ankle, right_ankle]), axis=0)
    torso = hips - shoulders
    body = ankles - nose
    torso_angle = np.arctan2(float(torso[1]), float(torso[0])) if not np.isnan(torso).any() else 0.0
    body_angle = np.arctan2(float(body[1]), float(body[0])) if not np.isnan(body).any() else 0.0

    flat_points = np.concatenate([norm_points, point_conf[:, None]], axis=1).reshape(-1)
    summary = np.array(
        [
            float(visible.mean()),
            float(point_conf.mean()),
            float(center[0]),
            float(center[1]),
            float(span[0]),
            float(span[1]),
            float(span[0] / max(span[1], 1e-6)),
            float(min_xy[1]),
            float(max_xy[1]),
            float(np.sin(torso_angle)),
            float(np.cos(torso_angle)),
            float(np.sin(body_angle)),
            float(np.cos(body_angle)),
            float(shoulders[1] if not np.isnan(shoulders).any() else 0.0),
            float(hips[1] if not np.isnan(hips).any() else 0.0),
            float(ankles[1] if not np.isnan(ankles).any() else 0.0),
            float(abs(torso[0]) if not np.isnan(torso).any() else 0.0),
            float(abs(torso[1]) if not np.isnan(torso).any() else 0.0),
        ],
        dtype=np.float32,
    )
    return np.concatenate([np.nan_to_num(flat_points, nan=0.0), summary]).astype(np.float32)


def aggregate_frame_features(frame_features: list[np.ndarray]) -> np.ndarray:
    matrix = np.stack(frame_features).astype(np.float32)
    return np.concatenate(
        [
            matrix.mean(axis=0),
            matrix.max(axis=0),
            matrix.std(axis=0),
            matrix[-1] - matrix[0],
        ],
        axis=0,
    ).astype(np.float32)


def main():
    args = parse_args()
    rows = load_manifest(Path(args.manifest))
    if args.max_windows > 0:
        rows = rows[: args.max_windows]

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Instale ultralytics: pip install -r requirements-ml.txt") from exc

    model = YOLO(args.pose_model)
    features = []
    labels = []
    for index, row in enumerate(rows, start=1):
        frame_features = []
        for frame_index in sample_frame_indices(
            int(row["start_frame"]),
            int(row["end_frame"]),
            args.frames_per_window,
        ):
            frame = read_frame(row["video_path"], frame_index)
            result = model.predict(frame, conf=args.confidence, verbose=False, device=args.device)[0]
            frame_features.append(best_person_keypoints(result, frame.shape))
        features.append(aggregate_frame_features(frame_features))
        labels.append(CLASS_TO_ID[row["label"]])
        if index == 1 or index % 25 == 0 or index == len(rows):
            print(f"YOLO Pose features {index}/{len(rows)}", flush=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "manifest": str(Path(args.manifest)),
        "pose_model": args.pose_model,
        "frames_per_window": args.frames_per_window,
        "confidence": args.confidence,
        "feature_type": "yolo_pose_window_stats",
        "feature_dimensions": int(len(features[0]) if features else 0),
        "feature_description": "COCO keypoints + pose geometry aggregated with mean/max/std/delta",
    }
    np.savez_compressed(
        output_path,
        x=np.stack(features).astype(np.float32),
        y=np.array(labels, dtype=np.int64),
        metadata=json.dumps(metadata),
    )
    print(f"Features YOLO Pose salvas em: {output_path}")


if __name__ == "__main__":
    main()
