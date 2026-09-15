from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import torch
import torch.nn as nn


PERSON_CLASS_ID = 0
COCO_KEYPOINTS = 17
PERSON_MASK_STATS_DIM = 8
POSE_FEATURE_DIM = COCO_KEYPOINTS * 3 + 18


class PersonMaskedBagClassifier(nn.Module):
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 256,
        dropout: float = 0.2,
        num_classes: int = 2,
        hidden_layers: int = 1,
    ):
        super().__init__()
        layers = []
        current_dim = input_dim
        for _ in range(max(1, int(hidden_layers))):
            layers.extend(
                [
                    nn.Linear(current_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                ]
            )
            current_dim = hidden_dim
        layers.append(nn.Linear(current_dim, num_classes))
        self.net = nn.Sequential(*layers)

    def forward(self, features):
        return self.net(features)


@dataclass(frozen=True)
class PersonMaskResult:
    frame: np.ndarray
    stats: np.ndarray


@dataclass(frozen=True)
class BagWindow:
    frames: list[np.ndarray]
    start_index: int
    end_index: int


def load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as jsonl_file:
        for line in jsonl_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise RuntimeError(f"Manifesto vazio: {path}")
    return rows


def sample_items(items: Sequence, count: int) -> list:
    if count <= 0:
        raise ValueError("count deve ser maior que zero.")
    item_list = list(items)
    if not item_list:
        return []
    if len(item_list) == 1:
        return [item_list[0]] * count
    indices = np.linspace(0, len(item_list) - 1, count).astype(int).tolist()
    sampled = [item_list[index] for index in indices]
    while len(sampled) < count:
        sampled.append(sampled[-1])
    return sampled[:count]


def read_video_segment_frames(
    video_path: str | Path,
    sample_fps: float,
    start_frame: int | None = None,
    end_frame: int | None = None,
) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    source_fps = float(cap.get(cv2.CAP_PROP_FPS) or sample_fps or 0.0)
    if total_frames <= 0:
        cap.release()
        raise RuntimeError(f"Video invalido ou sem frames: {video_path}")
    if sample_fps <= 0:
        cap.release()
        raise ValueError("sample_fps deve ser maior que zero.")

    start_idx = 0 if start_frame is None else max(0, int(start_frame))
    end_idx = total_frames - 1 if end_frame is None else min(total_frames - 1, int(end_frame))
    if end_idx < start_idx:
        cap.release()
        raise RuntimeError(f"Janela de frames invalida em: {video_path}")

    step = max(1, int(round(source_fps / sample_fps))) if source_fps > 0 else 1
    frames = []
    for frame_index in range(start_idx, end_idx + 1, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame_bgr = cap.read()
        if not ok:
            continue
        frames.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    cap.release()

    if not frames:
        raise RuntimeError(f"Nao foi possivel extrair frames: {video_path}")
    return frames


def split_bag_windows(
    frames: Sequence[np.ndarray],
    sample_fps: float,
    window_seconds: float,
    stride_seconds: float,
    min_window_seconds: float,
) -> list[BagWindow]:
    frame_list = list(frames)
    if not frame_list:
        return []
    if sample_fps <= 0:
        raise ValueError("sample_fps deve ser maior que zero.")
    if window_seconds <= 0:
        raise ValueError("window_seconds deve ser maior que zero.")
    if stride_seconds <= 0:
        raise ValueError("stride_seconds deve ser maior que zero.")

    min_frames = max(1, int(round(min_window_seconds * sample_fps)))
    full_window_frames = max(min_frames, int(round(window_seconds * sample_fps)))
    stride_frames = max(1, int(round(stride_seconds * sample_fps)))

    if len(frame_list) <= full_window_frames:
        return [BagWindow(frames=frame_list, start_index=0, end_index=len(frame_list) - 1)]

    windows = []
    start = 0
    while start < len(frame_list):
        end = min(len(frame_list), start + full_window_frames)
        if end - start >= min_frames:
            windows.append(BagWindow(frames=frame_list[start:end], start_index=start, end_index=end - 1))
        if end == len(frame_list):
            break
        start += stride_frames
    return windows


def aggregate_temporal_features(frame_features: Sequence[np.ndarray]) -> np.ndarray:
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


def aggregate_bag_features(window_features: Sequence[np.ndarray], top_k: int = 3) -> np.ndarray:
    matrix = np.stack(window_features).astype(np.float32)
    k = max(1, min(int(top_k), len(matrix)))
    topk_mean = np.sort(matrix, axis=0)[-k:].mean(axis=0)
    return np.concatenate(
        [
            matrix.mean(axis=0),
            matrix.max(axis=0),
            matrix.std(axis=0),
            matrix[-1] - matrix[0],
            topk_mean,
        ],
        axis=0,
    ).reshape(1, -1).astype(np.float32)


class PersonSegmenter:
    def __init__(
        self,
        model_path: str = "yolo11n-seg.pt",
        confidence: float = 0.25,
        background_mode: str = "mask_black",
        no_person_policy: str = "original",
        device: str | None = None,
    ):
        if background_mode not in {"mask_black"}:
            raise ValueError("background_mode suportado em v1: mask_black")
        if no_person_policy not in {"original", "zero"}:
            raise ValueError("no_person_policy deve ser original ou zero.")
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError("Person segmentation usa YOLO. Instale ultralytics.") from exc

        self.model_path = model_path
        self.confidence = float(confidence)
        self.background_mode = background_mode
        self.no_person_policy = no_person_policy
        self.device = device
        self.model = YOLO(model_path)

    def apply(self, frame: np.ndarray) -> PersonMaskResult:
        result = self.model.predict(
            frame,
            classes=[PERSON_CLASS_ID],
            conf=self.confidence,
            verbose=False,
            device=self.device,
        )[0]
        mask, stats = self._select_person_mask(result, frame.shape)
        if mask is None:
            if self.no_person_policy == "zero":
                return PersonMaskResult(np.zeros_like(frame), stats)
            return PersonMaskResult(frame.copy(), stats)

        masked = np.zeros_like(frame)
        masked[mask] = frame[mask]
        return PersonMaskResult(masked, stats)

    @staticmethod
    def empty_stats(detection_count: int = 0) -> np.ndarray:
        return np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, float(detection_count)], dtype=np.float32)

    def _select_person_mask(self, result, image_shape) -> tuple[np.ndarray | None, np.ndarray]:
        height, width = image_shape[:2]
        if (
            getattr(result, "masks", None) is None
            or result.masks is None
            or result.masks.data is None
            or getattr(result, "boxes", None) is None
            or result.boxes is None
            or len(result.boxes) == 0
        ):
            return None, self.empty_stats()

        masks = result.masks.data.detach().cpu().numpy()
        confs = result.boxes.conf.detach().cpu().numpy()
        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
        candidates = []
        for index, (mask, confidence, class_id) in enumerate(zip(masks, confs, classes)):
            if int(class_id) != PERSON_CLASS_ID:
                continue
            mask_bool = mask > 0.5
            if mask_bool.shape != (height, width):
                mask_bool = cv2.resize(
                    mask_bool.astype(np.uint8),
                    (width, height),
                    interpolation=cv2.INTER_NEAREST,
                ).astype(bool)
            area = float(mask_bool.mean())
            if area <= 0.0:
                continue
            candidates.append((float(confidence) * area, index, float(confidence), area, mask_bool))

        if not candidates:
            return None, self.empty_stats()

        _, _, confidence, area, mask_bool = max(candidates, key=lambda item: item[0])
        ys, xs = np.where(mask_bool)
        if len(xs) == 0:
            return None, self.empty_stats(len(candidates))

        x_min, x_max = float(xs.min()), float(xs.max())
        y_min, y_max = float(ys.min()), float(ys.max())
        stats = np.array(
            [
                1.0,
                confidence,
                area,
                ((x_min + x_max) / 2.0) / max(1.0, float(width)),
                ((y_min + y_max) / 2.0) / max(1.0, float(height)),
                (x_max - x_min + 1.0) / max(1.0, float(width)),
                (y_max - y_min + 1.0) / max(1.0, float(height)),
                float(len(candidates)),
            ],
            dtype=np.float32,
        )
        return mask_bool, stats


def empty_pose_feature() -> np.ndarray:
    return np.zeros(POSE_FEATURE_DIM, dtype=np.float32)


def select_pose_feature(result, image_shape) -> np.ndarray:
    height, width = image_shape[:2]
    if getattr(result, "keypoints", None) is None or result.keypoints is None:
        return empty_pose_feature()
    if result.keypoints.xy is None or len(result.keypoints.xy) == 0:
        return empty_pose_feature()

    xy = result.keypoints.xy.detach().cpu().numpy()
    conf = (
        result.keypoints.conf.detach().cpu().numpy()
        if result.keypoints.conf is not None
        else np.ones(xy.shape[:2])
    )
    if xy.shape[0] == 0:
        return empty_pose_feature()

    person_index = int(np.argmax(conf.mean(axis=1)))
    points = xy[person_index]
    point_conf = conf[person_index]
    norm_points = points / np.array([max(float(width), 1.0), max(float(height), 1.0)], dtype=np.float32)
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

    shoulders = nanmean_keypoints([kp(5), kp(6)])
    hips = nanmean_keypoints([kp(11), kp(12)])
    ankles = nanmean_keypoints([kp(15), kp(16)])
    nose = kp(0)
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


def nanmean_keypoints(points: Sequence[np.ndarray]) -> np.ndarray:
    matrix = np.stack(points).astype(np.float32)
    if np.isnan(matrix).all():
        return np.array([np.nan, np.nan], dtype=np.float32)
    return np.nanmean(matrix, axis=0).astype(np.float32)


def extract_pose_window_features(
    pose_model,
    frames: Sequence[np.ndarray],
    frames_per_window: int,
    confidence: float,
    device: str | None = None,
) -> np.ndarray:
    sampled = sample_items(frames, frames_per_window)
    frame_features = []
    for frame in sampled:
        result = pose_model.predict(frame, conf=confidence, verbose=False, device=device)[0]
        frame_features.append(select_pose_feature(result, frame.shape))
    return aggregate_temporal_features(frame_features)


@torch.no_grad()
def embed_masked_window(
    model,
    processor,
    frames: Sequence[np.ndarray],
    num_frames: int,
    device,
) -> np.ndarray:
    sampled = sample_items(frames, num_frames)
    inputs = processor(sampled, return_tensors="pt")
    pixel_values_videos = inputs["pixel_values_videos"].to(device)
    outputs = model(pixel_values_videos=pixel_values_videos, skip_predictor=True)
    tokens = outputs.last_hidden_state
    features = torch.cat([tokens.mean(dim=1), tokens.max(dim=1).values], dim=1)
    return features.squeeze(0).detach().cpu().numpy().astype(np.float32)


def mask_window_frames(
    segmenter: PersonSegmenter,
    frames: Sequence[np.ndarray],
) -> tuple[list[np.ndarray], np.ndarray]:
    masked_frames = []
    mask_stats = []
    for frame in frames:
        result = segmenter.apply(frame)
        masked_frames.append(result.frame)
        mask_stats.append(result.stats)
    return masked_frames, aggregate_temporal_features(mask_stats)


@torch.no_grad()
def extract_bag_feature_from_frames(
    frames: Sequence[np.ndarray],
    *,
    sample_fps: float,
    bag_window_seconds: float,
    bag_stride_seconds: float,
    min_window_seconds: float,
    num_frames: int,
    processor,
    jepa_model,
    device,
    segmenter: PersonSegmenter,
    pose_model,
    pose_frames_per_window: int,
    pose_confidence: float,
    top_k: int = 3,
    include_original_jepa: bool = False,
) -> tuple[np.ndarray, dict]:
    windows = split_bag_windows(
        frames,
        sample_fps=sample_fps,
        window_seconds=bag_window_seconds,
        stride_seconds=bag_stride_seconds,
        min_window_seconds=min_window_seconds,
    )
    if not windows:
        raise ValueError("Nao ha frames suficientes para formar janelas do bag.")

    window_features = []
    for window in windows:
        masked_frames, mask_features = mask_window_frames(segmenter, window.frames)
        feature_parts = []
        if include_original_jepa:
            feature_parts.append(embed_masked_window(jepa_model, processor, window.frames, num_frames, device))
        jepa_features = embed_masked_window(jepa_model, processor, masked_frames, num_frames, device)
        feature_parts.append(jepa_features)
        pose_features = extract_pose_window_features(
            pose_model,
            window.frames,
            frames_per_window=pose_frames_per_window,
            confidence=pose_confidence,
            device=str(device) if device is not None else None,
        )
        feature_parts.extend([pose_features, mask_features])
        window_features.append(np.concatenate(feature_parts).astype(np.float32))

    features = aggregate_bag_features(window_features, top_k=top_k)
    info = {
        "bag_window_count": len(windows),
        "window_feature_dimensions": int(len(window_features[0])),
        "bag_feature_dimensions": int(features.shape[1]),
        "include_original_jepa": bool(include_original_jepa),
    }
    return features, info
