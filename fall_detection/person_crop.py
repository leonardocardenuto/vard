"""Experimental, window-stable person crop before the fall classifier."""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np


def crop_window(frames, boxes, *, margin=0.25, size=256):
    if not frames:
        raise ValueError("Janela de frames vazia.")
    height, width = frames[0].shape[:2]
    if any(frame.shape != frames[0].shape for frame in frames):
        raise ValueError("Todos os frames devem ter a mesma dimensao.")
    if not math.isfinite(margin) or margin < 0 or size < 1:
        raise ValueError("Margem ou tamanho de recorte invalido.")
    valid = []
    for box in boxes:
        if len(box) != 4 or not all(math.isfinite(float(v)) for v in box):
            continue
        x1, y1, x2, y2 = box
        x1, x2 = max(0, x1), min(width, x2)
        y1, y2 = max(0, y1), min(height, y2)
        if x2 > x1 and y2 > y1:
            valid.append((x1, y1, x2, y2))
    if not valid:
        return frames, None
    # Union across people and time preserves displacement and avoids crop jitter.
    left, top = min(b[0] for b in valid), min(b[1] for b in valid)
    right, bottom = max(b[2] for b in valid), max(b[3] for b in valid)
    dx, dy = (right - left) * margin, (bottom - top) * margin
    left, top = max(0, math.floor(left - dx)), max(0, math.floor(top - dy))
    right, bottom = min(width, math.ceil(right + dx)), min(height, math.ceil(bottom + dy))
    result = []
    for frame in frames:
        crop = frame[top:bottom, left:right]
        scale = size / max(crop.shape[:2])
        w, h = max(1, round(crop.shape[1] * scale)), max(1, round(crop.shape[0] * scale))
        resized = cv2.resize(crop, (w, h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
        output = np.zeros((size, size, 3), dtype=frame.dtype)
        x, y = (size - w) // 2, (size - h) // 2
        output[y:y + h, x:x + w] = resized
        result.append(output)
    return result, (left, top, right, bottom)


class PersonWindowCropper:
    def __init__(self, checkpoint: str, device: str | None = None):
        self.checkpoint = Path(checkpoint)
        self.device = device
        self._model = None

    def apply(self, frames):
        boxes, _ = self.analyze(frames, include_pose=False)
        return crop_window(frames, boxes)

    def analyze(self, frames, *, include_pose=True):
        if self._model is None:
            if not self.checkpoint.is_file():
                raise FileNotFoundError(f"Modelo de recorte ausente: {self.checkpoint}. Use --person-crop-model.")
            from ultralytics import YOLO

            self._model = YOLO(str(self.checkpoint))
        boxes, poses = [], []
        ambiguous = False
        for frame in frames:
            # OpenCV/Ultralytics array inputs are BGR; classifier inputs are RGB.
            predictions = self._model.predict(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                classes=[0], conf=0.25, device=self.device, verbose=False)
            frame_poses = []
            person_count = 0
            for prediction in predictions:
                if prediction.boxes is not None:
                    detected = prediction.boxes.xyxy.cpu().numpy().tolist()
                    boxes.extend(detected)
                    person_count += len(detected)
                keypoints = getattr(prediction, "keypoints", None) if include_pose else None
                if keypoints is not None:
                    frame_poses.extend(keypoints.data.cpu().numpy().tolist())
            # Until tracking is validated, never mix different people's joints.
            ambiguous = ambiguous or person_count > 1
            poses.append(frame_poses[0] if person_count == 1 and len(frame_poses) == 1 else None)
        return boxes, [None] * len(poses) if ambiguous else poses
