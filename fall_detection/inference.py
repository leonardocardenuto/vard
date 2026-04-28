from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
from transformers import AutoVideoProcessor

LOGGER = logging.getLogger(__name__)


def _load_training_symbols():
    repo_root = Path(__file__).resolve().parents[1]
    tests_dir = repo_root / "tests"
    if str(tests_dir) not in sys.path:
        sys.path.insert(0, str(tests_dir))

    from train_fall_classifier import (
        CLASS_NAMES,
        MODEL_NAME,
        VJEPA2Classifier,
        read_video_frames_opencv,
    )

    return CLASS_NAMES, MODEL_NAME, VJEPA2Classifier, read_video_frames_opencv


CLASS_NAMES, MODEL_NAME, VJEPA2Classifier, read_video_frames_opencv = _load_training_symbols()


class FallClassifier:
    def __init__(
        self,
        checkpoint: str | Path,
        device: str | None = None,
        freeze_backbone: bool = True,
    ):
        self.checkpoint = Path(checkpoint)
        if not self.checkpoint.exists():
            raise FileNotFoundError(f"Checkpoint nao encontrado: {self.checkpoint}")

        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        LOGGER.info("Usando device: %s", self.device)
        LOGGER.info("Carregando processor do modelo: %s", MODEL_NAME)
        self.processor = AutoVideoProcessor.from_pretrained(MODEL_NAME)

        LOGGER.info("Carregando modelo V-JEPA2 e checkpoint: %s", self.checkpoint)
        self.model = VJEPA2Classifier(
            model_name=MODEL_NAME,
            num_classes=len(CLASS_NAMES),
            freeze_backbone=freeze_backbone,
        ).to(self.device)
        state_dict = torch.load(self.checkpoint, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()
        LOGGER.info("Modelo pronto para inferencia.")

    @torch.no_grad()
    def predict_frames(self, frames: Sequence[np.ndarray]) -> dict:
        if not frames:
            raise ValueError("predict_frames recebeu uma lista vazia de frames.")

        inputs = self.processor(list(frames), return_tensors="pt")
        pixel_values_videos = inputs["pixel_values_videos"].to(self.device)

        logits = self.model(pixel_values_videos)
        probs = torch.softmax(logits, dim=1).squeeze(0).detach().cpu().tolist()
        pred_idx = int(torch.argmax(logits, dim=1).item())
        probabilities = {
            class_name: float(probability)
            for class_name, probability in zip(CLASS_NAMES, probs)
        }

        fall_probability = probabilities.get("queda", probs[-1] if probs else 0.0)
        result = {
            "predicted_class": CLASS_NAMES[pred_idx],
            "probabilities": probabilities,
            "fall_probability": float(fall_probability),
        }
        LOGGER.info(
            "Inferencia realizada: classe=%s probabilidades=%s queda=%.4f",
            result["predicted_class"],
            probabilities,
            result["fall_probability"],
        )
        return result

    def predict_video_file(
        self,
        video_path: str | Path,
        num_frames: int = 16,
        start_frame: int | None = None,
        end_frame: int | None = None,
    ) -> dict:
        clip_path = Path(video_path)
        if not clip_path.exists():
            raise FileNotFoundError(f"Video nao encontrado: {clip_path}")

        LOGGER.info(
            "Lendo video para inferencia unica: path=%s num_frames=%s start_frame=%s end_frame=%s",
            clip_path,
            num_frames,
            start_frame,
            end_frame,
        )
        frames = read_video_frames_opencv(
            str(clip_path),
            num_frames=num_frames,
            start_frame=start_frame,
            end_frame=end_frame,
        )
        LOGGER.info("Frames extraidos do video: %s", len(frames))
        return self.predict_frames(frames)
