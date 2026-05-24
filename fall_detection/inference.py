from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Sequence

import cv2
import joblib
import numpy as np
import torch
from transformers import AutoModel, AutoVideoProcessor

LOGGER = logging.getLogger(__name__)


def _prepare_huggingface_cache() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    cache_dir = repo_root / ".cache" / "huggingface"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Evita erros de permissao ao tentar gravar no cache global do usuario.
    os.environ.setdefault("HF_HOME", str(cache_dir))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_dir / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_dir / "transformers"))
    return cache_dir


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
HF_CACHE_DIR = _prepare_huggingface_cache()


class FallClassifier:
    def __init__(
        self,
        checkpoint: str | Path,
        device: str | None = None,
        freeze_backbone: bool = True,
    ):
        self.checkpoint = self._resolve_checkpoint_path(checkpoint)
        if not self.checkpoint.exists():
            raise FileNotFoundError(f"Checkpoint nao encontrado: {self.checkpoint}")

        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.class_names = list(CLASS_NAMES)
        self.mode = "torch_head"
        self.embedding_feature_strategy = "mean"
        LOGGER.info("Usando device: %s", self.device)
        LOGGER.info("Carregando processor do modelo: %s", MODEL_NAME)
        self.processor = AutoVideoProcessor.from_pretrained(MODEL_NAME, cache_dir=HF_CACHE_DIR)

        if self.checkpoint.suffix.lower() == ".pkl":
            self._load_embedding_pipeline_checkpoint(freeze_backbone=freeze_backbone)
        else:
            self._load_torch_classifier_checkpoint(freeze_backbone=freeze_backbone)

    @staticmethod
    def _resolve_checkpoint_path(checkpoint: str | Path) -> Path:
        checkpoint_path = Path(checkpoint)
        if checkpoint_path.exists():
            return checkpoint_path

        repo_root = Path(__file__).resolve().parents[1]
        candidates = [
            repo_root / checkpoint_path,
            repo_root / "fall_detection" / checkpoint_path.name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        return checkpoint_path

    def _load_torch_classifier_checkpoint(self, freeze_backbone: bool):
        LOGGER.info("Carregando modelo V-JEPA2 com head treinada: %s", self.checkpoint)
        self.model = VJEPA2Classifier(
            model_name=MODEL_NAME,
            num_classes=len(self.class_names),
            freeze_backbone=freeze_backbone,
            cache_dir=HF_CACHE_DIR,
        ).to(self.device)
        state_dict = torch.load(self.checkpoint, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()
        LOGGER.info("Checkpoint PyTorch carregado com sucesso.")

    def _load_embedding_pipeline_checkpoint(self, freeze_backbone: bool):
        LOGGER.info("Carregando pipeline de embeddings + sklearn: %s", self.checkpoint)
        checkpoint_data = joblib.load(self.checkpoint)
        if not isinstance(checkpoint_data, dict) or "model" not in checkpoint_data:
            raise ValueError(
                f"Checkpoint .pkl invalido: esperado dict com chave 'model', recebido {type(checkpoint_data)!r}"
            )

        metadata = checkpoint_data.get("metadata") or {}
        backbone_name = metadata.get("backbone", MODEL_NAME)
        metadata_class_names = metadata.get("class_names")
        if metadata_class_names:
            self.class_names = list(metadata_class_names)

        self.mode = "embedding_sklearn"
        self.embedding_pipeline = checkpoint_data["model"]
        self.model = AutoModel.from_pretrained(backbone_name, cache_dir=HF_CACHE_DIR).to(self.device)
        self.model.eval()
        if freeze_backbone:
            for param in self.model.parameters():
                param.requires_grad = False

        hidden_size = int(self.model.config.hidden_size)
        expected_features = getattr(self.embedding_pipeline, "n_features_in_", None)
        if expected_features is None and hasattr(self.embedding_pipeline, "named_steps"):
            scaler = self.embedding_pipeline.named_steps.get("standardscaler")
            expected_features = getattr(scaler, "n_features_in_", None)

        if expected_features in (None, hidden_size):
            self.embedding_feature_strategy = "mean"
        elif expected_features == hidden_size * 2:
            self.embedding_feature_strategy = "mean_std"
        else:
            raise ValueError(
                "Nao consegui inferir a estrategia de embeddings para o checkpoint sklearn: "
                f"hidden_size={hidden_size} expected_features={expected_features}"
            )

        LOGGER.info(
            "Checkpoint sklearn carregado. backbone=%s classes=%s feature_strategy=%s",
            backbone_name,
            self.class_names,
            self.embedding_feature_strategy,
        )

    @staticmethod
    def _pool_embedding_features(last_hidden_state: torch.Tensor, strategy: str) -> np.ndarray:
        if strategy == "mean":
            features = last_hidden_state.mean(dim=1)
        elif strategy == "mean_std":
            features_mean = last_hidden_state.mean(dim=1)
            features_std = last_hidden_state.std(dim=1, unbiased=False)
            features = torch.cat([features_mean, features_std], dim=1)
        else:
            raise ValueError(f"Estrategia de pooling nao suportada: {strategy}")

        return features.detach().cpu().numpy()

    @torch.no_grad()
    def predict_frames(self, frames: Sequence[np.ndarray]) -> dict:
        if not frames:
            raise ValueError("predict_frames recebeu uma lista vazia de frames.")

        inputs = self.processor(list(frames), return_tensors="pt")
        pixel_values_videos = inputs["pixel_values_videos"].to(self.device)

        if self.mode == "embedding_sklearn":
            outputs = self.model(pixel_values_videos=pixel_values_videos, skip_predictor=True)
            features = self._pool_embedding_features(
                outputs.last_hidden_state,
                self.embedding_feature_strategy,
            )
            if hasattr(self.embedding_pipeline, "predict_proba"):
                probs = self.embedding_pipeline.predict_proba(features)[0].tolist()
            else:
                pred_idx = int(self.embedding_pipeline.predict(features)[0])
                probs = [0.0] * len(self.class_names)
                if 0 <= pred_idx < len(probs):
                    probs[pred_idx] = 1.0
            pred_idx = int(np.argmax(probs))
        else:
            logits = self.model(pixel_values_videos)
            probs = torch.softmax(logits, dim=1).squeeze(0).detach().cpu().tolist()
            pred_idx = int(torch.argmax(logits, dim=1).item())

        probabilities = {
            class_name: float(probability)
            for class_name, probability in zip(self.class_names, probs)
        }

        fall_probability = probabilities.get("queda", probs[-1] if probs else 0.0)
        result = {
            "predicted_class": self.class_names[pred_idx],
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

    def predict_video_windows(
        self,
        video_path: str | Path,
        num_frames: int = 16,
        sample_fps: float = 6.0,
        stride_seconds: float = 1.0,
        start_frame: int | None = None,
        end_frame: int | None = None,
    ) -> list[dict]:
        if num_frames <= 0:
            raise ValueError("num_frames deve ser maior que zero.")
        if sample_fps <= 0:
            raise ValueError("sample_fps deve ser maior que zero.")
        if stride_seconds <= 0:
            raise ValueError("stride_seconds deve ser maior que zero.")

        clip_path = Path(video_path)
        if not clip_path.exists():
            raise FileNotFoundError(f"Video nao encontrado: {clip_path}")

        cap = cv2.VideoCapture(str(clip_path))
        if not cap.isOpened():
            raise RuntimeError(f"Nao foi possivel abrir o video: {clip_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        cap.release()

        if total_frames <= 0:
            raise RuntimeError(f"Video invalido ou sem frames: {clip_path}")
        if fps <= 0:
            raise RuntimeError(f"Nao foi possivel determinar o FPS do video: {clip_path}")

        start_idx = 0 if start_frame is None else max(0, start_frame)
        end_idx = total_frames - 1 if end_frame is None else min(total_frames - 1, end_frame)
        if end_idx < start_idx:
            raise RuntimeError(f"Janela de frames invalida em: {clip_path}")

        window_span_frames = max(
            num_frames,
            int(round(((num_frames - 1) / sample_fps) * fps)) + 1,
        )
        stride_frames = max(1, int(round(stride_seconds * fps)))

        windows: list[tuple[int, int]] = []
        current_start = start_idx
        max_start = max(start_idx, end_idx - window_span_frames + 1)

        while current_start <= max_start:
            current_end = min(current_start + window_span_frames - 1, end_idx)
            windows.append((current_start, current_end))
            current_start += stride_frames

        if not windows:
            windows.append((start_idx, end_idx))
        elif windows[-1][1] < end_idx:
            final_start = max(start_idx, end_idx - window_span_frames + 1)
            final_window = (final_start, end_idx)
            if final_window != windows[-1]:
                windows.append(final_window)

        LOGGER.info(
            "Analisando video em janelas deslizantes: path=%s fps=%.3f total_frames=%s window_span_frames=%s stride_frames=%s windows=%s",
            clip_path,
            fps,
            total_frames,
            window_span_frames,
            stride_frames,
            len(windows),
        )

        results = []
        for window_index, (window_start, window_end) in enumerate(windows, start=1):
            prediction = self.predict_video_file(
                clip_path,
                num_frames=num_frames,
                start_frame=window_start,
                end_frame=window_end,
            )
            results.append(
                {
                    "window_index": window_index,
                    "start_frame": window_start,
                    "end_frame": window_end,
                    "start_time_seconds": window_start / fps,
                    "end_time_seconds": window_end / fps,
                    **prediction,
                }
            )

        return results
