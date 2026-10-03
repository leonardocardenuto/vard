from __future__ import annotations

from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import torch
from transformers import AutoModel, AutoVideoProcessor

from .confrontation_model import CLASS_NAMES, ConfrontationHead
from .inference import FallClassifier, HF_CACHE_DIR


class ConfrontationClassifier(FallClassifier):
    """Mesmo encoder congelado, pooling e MLP do treino binario de quedas."""

    def __init__(self, checkpoint: str | Path, device: str | None = None):
        self.checkpoint = self._resolve_checkpoint_path(checkpoint)
        data = torch.load(self.checkpoint, map_location="cpu", weights_only=True)
        required = {"head_state_dict", "model_name", "class_names", "input_dim", "hidden_dim",
                    "dropout", "num_frames", "view_duration_seconds", "head_architecture"}
        if not isinstance(data, dict) or not required.issubset(data):
            raise ValueError("Checkpoint de confronto invalido: metadados/head ausentes.")
        self.class_names = list(data["class_names"])
        if len(self.class_names) != 2 or set(self.class_names) != set(CLASS_NAMES):
            raise ValueError(f"Classes do checkpoint de confronto invalidas: {self.class_names}")
        if data["head_architecture"] != "fall_mlp_relu":
            raise ValueError("Arquitetura da head de confronto incompativel.")
        self.num_frames = int(data["num_frames"])
        self.view_duration_seconds = float(data["view_duration_seconds"])
        self.max_frame_side = int(data.get("max_frame_side", 960))
        self.recommended_threshold = float(data.get("recommended_threshold", 0.5))
        if self.num_frames < 2 or self.view_duration_seconds <= 0 or self.max_frame_side < 1:
            raise ValueError("Janela temporal/dimensao do checkpoint de confronto invalida.")
        if not 0 <= self.recommended_threshold <= 1:
            raise ValueError("Limiar do checkpoint de confronto invalido.")
        self.sample_fps = (self.num_frames - 1) / self.view_duration_seconds
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.head = ConfrontationHead(int(data["input_dim"]), int(data["hidden_dim"]), float(data["dropout"]))
        self.head.load_state_dict(data["head_state_dict"], strict=True)
        self.head.to(self.device).eval()
        self.processor = AutoVideoProcessor.from_pretrained(data["model_name"], cache_dir=HF_CACHE_DIR)
        self.model = AutoModel.from_pretrained(data["model_name"], cache_dir=HF_CACHE_DIR).to(self.device)
        if int(self.model.config.hidden_size) != int(data["input_dim"]):
            raise ValueError("Dimensao do backbone incompativel com a head de confronto.")
        self.model.eval().requires_grad_(False)

    @torch.inference_mode()
    def predict_frames(self, frames: Sequence[np.ndarray]) -> dict:
        if len(frames) != self.num_frames:
            raise ValueError(f"Checkpoint de confronto requer {self.num_frames} frames; recebidos {len(frames)}.")
        resized = []
        for frame in frames:
            height, width = frame.shape[:2]
            scale = min(1.0, self.max_frame_side / max(height, width))
            resized.append(cv2.resize(frame, (max(1, round(width * scale)), max(1, round(height * scale))),
                                      interpolation=cv2.INTER_AREA) if scale < 1 else frame)
        pixels = self.processor(resized, return_tensors="pt")["pixel_values_videos"].to(self.device)
        # A extracao de embeddings do treinamento usa BF16 na GPU e FP32 na CPU.
        with torch.autocast(device_type=self.device.type, dtype=torch.bfloat16, enabled=self.device.type == "cuda"):
            outputs = self.model(pixel_values_videos=pixels, skip_predictor=True)
            features = outputs.last_hidden_state.mean(dim=1).float()
        probs = self.head(features).softmax(dim=1)[0].cpu().tolist()
        probabilities = dict(zip(self.class_names, probs))
        return {"predicted_class": self.class_names[int(np.argmax(probs))],
                "probabilities": probabilities,
                "confrontation_probability": float(probabilities["confronto"])}

    def predict_video_file(self, video_path, num_frames=None, start_frame=None, end_frame=None) -> dict:
        if num_frames is not None and num_frames != self.num_frames:
            raise ValueError(f"Checkpoint de confronto requer {self.num_frames} frames.")
        if not Path(video_path).exists():
            raise FileNotFoundError(f"Video nao encontrado: {video_path}")
        cap = cv2.VideoCapture(str(video_path))
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        finally:
            cap.release()
        if fps <= 0 or total_frames < self.num_frames:
            raise ValueError("Video ilegivel ou sem frames suficientes.")
        start = max(0, start_frame or 0)
        end = min(total_frames - 1, start + round(self.view_duration_seconds * fps) - 1
                  if end_frame is None else end_frame)
        span = end - start + 1
        if span < self.num_frames or not self.view_duration_seconds * 0.9 <= span / fps <= self.view_duration_seconds * 1.1:
            raise ValueError("Janela do video incompativel com a duracao do checkpoint de confronto.")
        return super().predict_video_file(video_path, num_frames=self.num_frames, start_frame=start, end_frame=end)

    def predict_video_windows(self, video_path, num_frames=None, sample_fps=None,
                              stride_seconds=1.0, start_frame=None, end_frame=None) -> list[dict]:
        frames = self.num_frames if num_frames is None else num_frames
        fps = self.sample_fps if sample_fps is None else sample_fps
        if frames != self.num_frames or abs(fps - self.sample_fps) > 1e-6:
            raise ValueError("Janela de confronto deve corresponder aos metadados do treinamento.")
        return super().predict_video_windows(video_path, num_frames=frames, sample_fps=fps,
                                            stride_seconds=stride_seconds, start_frame=start_frame, end_frame=end_frame)
