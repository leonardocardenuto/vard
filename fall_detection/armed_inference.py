from __future__ import annotations

from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import torch
from torch import nn
from transformers import AutoModel, AutoVideoProcessor

from .inference import FallClassifier, HF_CACHE_DIR


class ArmedClassifierHead(nn.Module):
    """Arquitetura salva por train_gun_classifier_head.py, sem importar o treino."""

    def __init__(self, input_dim: int, hidden_dim: int, dropout: float):
        super().__init__()
        self.network = nn.Sequential(
            nn.LayerNorm(input_dim),
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 2),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


class ArmedClassifier(FallClassifier):
    """V-JEPA 2 congelado + head binaria, com os metadados do checkpoint."""

    def __init__(self, checkpoint: str | Path, device: str | None = None):
        self.checkpoint = self._resolve_checkpoint_path(checkpoint)
        data = torch.load(self.checkpoint, map_location="cpu", weights_only=True)
        required = {"head_state_dict", "model_name", "class_names", "input_dim",
                    "hidden_dim", "dropout", "num_frames", "view_duration_seconds"}
        if not isinstance(data, dict) or not required.issubset(data):
            raise ValueError("Checkpoint de pessoas armadas invalido: metadados/head ausentes.")
        self.class_names = list(data["class_names"])
        if len(self.class_names) != 2 or set(self.class_names) != {"sem_arma", "armado"}:
            raise ValueError(f"Classes do checkpoint de armas invalidas: {self.class_names}")
        self.num_frames = int(data["num_frames"])
        self.view_duration_seconds = float(data["view_duration_seconds"])
        if self.num_frames < 2 or self.view_duration_seconds <= 0:
            raise ValueError("A janela temporal do checkpoint de armas e invalida.")
        self.sample_fps = (self.num_frames - 1) / self.view_duration_seconds
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.head = ArmedClassifierHead(data["input_dim"], data["hidden_dim"], data["dropout"])
        self.head.load_state_dict(data["head_state_dict"], strict=True)
        self.head.to(self.device).eval()
        self.processor = AutoVideoProcessor.from_pretrained(data["model_name"], cache_dir=HF_CACHE_DIR)
        self.model = AutoModel.from_pretrained(data["model_name"], cache_dir=HF_CACHE_DIR).to(self.device)
        if int(self.model.config.hidden_size) != int(data["input_dim"]):
            raise ValueError("Dimensao do backbone incompativel com a head de armas.")
        self.model.eval().requires_grad_(False)

    @torch.no_grad()
    def predict_frames(self, frames: Sequence[np.ndarray]) -> dict:
        if len(frames) != self.num_frames:
            raise ValueError(f"Checkpoint de armas requer {self.num_frames} frames; recebidos {len(frames)}.")
        # O treino limita o maior lado antes do AutoVideoProcessor.
        resized = []
        for frame in frames:
            height, width = frame.shape[:2]
            scale = min(1.0, 960 / max(height, width))
            resized.append(cv2.resize(
                frame, (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            ) if scale < 1 else frame)
        inputs = self.processor(resized, return_tensors="pt")
        pixels = inputs["pixel_values_videos"].to(self.device)
        outputs = self.model(pixel_values_videos=pixels, skip_predictor=True)
        features = outputs.last_hidden_state.mean(dim=1).float()
        probs = self.head(features).softmax(dim=1)[0].cpu().tolist()
        probabilities = dict(zip(self.class_names, probs))
        return {
            "predicted_class": self.class_names[int(np.argmax(probs))],
            "probabilities": probabilities,
            "armed_probability": float(probabilities["armado"]),
        }

    def predict_video_file(self, video_path, num_frames=None, start_frame=None, end_frame=None) -> dict:
        return super().predict_video_file(
            video_path, num_frames=self.num_frames if num_frames is None else num_frames,
            start_frame=start_frame, end_frame=end_frame,
        )

    def predict_video_windows(self, video_path, num_frames=None, sample_fps=None,
                              stride_seconds=1.0, start_frame=None, end_frame=None) -> list[dict]:
        return super().predict_video_windows(
            video_path, num_frames=self.num_frames if num_frames is None else num_frames,
            sample_fps=self.sample_fps if sample_fps is None else sample_fps,
            stride_seconds=stride_seconds, start_frame=start_frame, end_frame=end_frame,
        )
