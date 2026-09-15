from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np


CLASS_TO_ID = {"sem_queda": 0, "queda": 1}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai features auxiliares YOLO/OBB por janela para concatenar com V-JEPA."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--yolo-model", default="yolo11n-obb.pt")
    parser.add_argument("--frames-per-window", type=int, default=8)
    parser.add_argument("--confidence", type=float, default=0.15)
    parser.add_argument(
        "--class-filter",
        default=None,
        help="IDs de classe separados por virgula. Ex: 0 para pessoa em modelos detect; vazio usa todas.",
    )
    parser.add_argument("--device", default=None)
    parser.add_argument("--max-windows", type=int, default=0)
    parser.add_argument(
        "--feature-version",
        choices=["legacy_v1", "semantic_v2"],
        default="semantic_v2",
        help="legacy_v1 gera 48 dims; semantic_v2 adiciona geometria corporal e gera 72 dims.",
    )
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


def parse_class_filter(value: str | None) -> set[int] | None:
    if not value:
        return None
    return {int(item.strip()) for item in value.split(",") if item.strip()}


def sample_frame_indices(start_frame: int, end_frame: int, count: int) -> list[int]:
    if end_frame < start_frame:
        raise ValueError("Janela invalida.")
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


def _empty_detection_feature(feature_version: str) -> np.ndarray:
    return np.zeros(18 if feature_version == "semantic_v2" else 12, dtype=np.float32)


def _select_best_detection(result, class_filter: set[int] | None, image_shape, feature_version: str) -> np.ndarray:
    height, width = image_shape[:2]
    detections = []

    if getattr(result, "obb", None) is not None and result.obb is not None and len(result.obb) > 0:
        xywhr = result.obb.xywhr.detach().cpu().numpy()
        confs = result.obb.conf.detach().cpu().numpy()
        classes = result.obb.cls.detach().cpu().numpy().astype(int)
        for box, conf, cls in zip(xywhr, confs, classes):
            if class_filter is not None and cls not in class_filter:
                continue
            cx, cy, bw, bh, angle = [float(value) for value in box]
            detections.append((float(conf), int(cls), cx, cy, bw, bh, angle))

    elif getattr(result, "boxes", None) is not None and result.boxes is not None and len(result.boxes) > 0:
        xywh = result.boxes.xywh.detach().cpu().numpy()
        confs = result.boxes.conf.detach().cpu().numpy()
        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
        for box, conf, cls in zip(xywh, confs, classes):
            if class_filter is not None and cls not in class_filter:
                continue
            cx, cy, bw, bh = [float(value) for value in box]
            detections.append((float(conf), int(cls), cx, cy, bw, bh, 0.0))

    if not detections:
        return _empty_detection_feature(feature_version)

    conf, cls, cx, cy, bw, bh, angle = max(detections, key=lambda item: item[0] * item[4] * item[5])
    norm_w = max(1.0, float(width))
    norm_h = max(1.0, float(height))
    area = (bw * bh) / (norm_w * norm_h)
    aspect = bw / max(1.0, bh)
    angle_sin = math.sin(angle)
    angle_cos = math.cos(angle)
    base = [
        1.0,
        conf,
        cx / norm_w,
        cy / norm_h,
        bw / norm_w,
        bh / norm_h,
        area,
        aspect,
        angle_sin,
        angle_cos,
        float(cls),
        float(len(detections)),
    ]
    if feature_version == "legacy_v1":
        return np.array(base, dtype=np.float32)

    norm_bw = bw / norm_w
    norm_bh = bh / norm_h
    top_y = max(0.0, (cy - bh / 2.0) / norm_h)
    bottom_y = min(1.0, (cy + bh / 2.0) / norm_h)
    long_side = max(norm_bw, norm_bh)
    short_side = min(norm_bw, norm_bh)
    elongation = long_side / max(1e-6, short_side)
    horizontal_extent_ratio = norm_bw / max(1e-6, norm_bw + norm_bh)
    return np.array(
        base
        + [
            top_y,
            bottom_y,
            long_side,
            short_side,
            elongation,
            horizontal_extent_ratio,
        ],
        dtype=np.float32,
    )


def aggregate_frame_features(frame_features: list[np.ndarray]) -> np.ndarray:
    matrix = np.stack(frame_features).astype(np.float32)
    first = matrix[0]
    last = matrix[-1]
    return np.concatenate(
        [
            matrix.mean(axis=0),
            matrix.max(axis=0),
            matrix.std(axis=0),
            last - first,
        ],
        axis=0,
    ).astype(np.float32)


def main():
    args = parse_args()
    rows = load_manifest(Path(args.manifest))
    if args.max_windows > 0:
        rows = rows[: args.max_windows]
    class_filter = parse_class_filter(args.class_filter)

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Instale ultralytics: pip install -r requirements-ml.txt") from exc

    model = YOLO(args.yolo_model)
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
            result = model.predict(
                frame,
                conf=args.confidence,
                verbose=False,
                device=args.device,
            )[0]
            frame_features.append(_select_best_detection(result, class_filter, frame.shape, args.feature_version))
        features.append(aggregate_frame_features(frame_features))
        labels.append(CLASS_TO_ID[row["label"]])
        if index == 1 or index % 25 == 0 or index == len(rows):
            print(f"YOLO OBB features {index}/{len(rows)}", flush=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "manifest": str(Path(args.manifest)),
        "yolo_model": args.yolo_model,
        "frames_per_window": args.frames_per_window,
        "confidence": args.confidence,
        "class_filter": sorted(class_filter) if class_filter is not None else None,
        "feature_version": args.feature_version,
        "feature_description": (
            "per-frame best OBB/box stats aggregated with mean/max/std/delta; "
            "semantic_v2 adds top/bottom, long/short side, elongation and horizontal extent"
        ),
    }
    np.savez_compressed(
        output_path,
        x=np.stack(features).astype(np.float32),
        y=np.array(labels, dtype=np.int64),
        metadata=json.dumps(metadata),
    )
    print(f"Features YOLO/OBB salvas em: {output_path}")


if __name__ == "__main__":
    main()
