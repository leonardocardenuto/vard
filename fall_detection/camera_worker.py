from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterator

import cv2

LOGGER = logging.getLogger(__name__)


class CameraWorker:
    def __init__(
        self,
        source: str | int,
        sample_fps: float = 6.0,
        reconnect_delay: float = 2.0,
        max_reconnect_attempts: int | None = None,
        webcam_backend: str = "auto",
    ):
        if sample_fps <= 0:
            raise ValueError("sample_fps deve ser maior que zero.")
        self.source = self._normalize_source(source)
        self.sample_fps = sample_fps
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        self.webcam_backend = webcam_backend.lower()
        self._cap: cv2.VideoCapture | None = None
        self._captured_frames = 0

    @staticmethod
    def _normalize_source(source: str | int) -> str | int:
        if isinstance(source, int):
            return source
        source_text = str(source).strip()
        if source_text.isdigit():
            return int(source_text)
        return source_text

    @property
    def is_stream(self) -> bool:
        return isinstance(self.source, int) or str(self.source).lower().startswith(("rtsp://", "rtmp://", "http://", "https://"))

    @property
    def captured_frames(self) -> int:
        return self._captured_frames

    def open(self):
        if isinstance(self.source, str) and not self.is_stream and not Path(self.source).exists():
            raise FileNotFoundError(f"Fonte de video nao encontrada: {self.source}")

        LOGGER.info("Conectando fonte de camera/video: %s", self.source)
        self._cap = self._open_capture()
        if not self._cap.isOpened():
            self.release()
            raise RuntimeError(f"Nao foi possivel abrir a fonte: {self.source}")
        LOGGER.info("Fonte conectada com sucesso.")

    def _open_capture(self) -> cv2.VideoCapture:
        if not isinstance(self.source, int):
            return cv2.VideoCapture(self.source)

        if self.webcam_backend == "dshow":
            LOGGER.info("Abrindo webcam com backend DirectShow.")
            return cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
        if self.webcam_backend == "msmf":
            LOGGER.info("Abrindo webcam com backend Media Foundation.")
            return cv2.VideoCapture(self.source, cv2.CAP_MSMF)

        if self.webcam_backend == "auto":
            for backend_name, backend in (("DirectShow", cv2.CAP_DSHOW), ("Media Foundation", cv2.CAP_MSMF)):
                LOGGER.info("Tentando abrir webcam com backend %s.", backend_name)
                cap = cv2.VideoCapture(self.source, backend)
                if cap.isOpened():
                    LOGGER.info("Webcam aberta com backend %s.", backend_name)
                    return cap
                cap.release()

        LOGGER.info("Voltando para backend padrao do OpenCV para webcam.")
        return cv2.VideoCapture(self.source)

    def release(self):
        if self._cap is not None:
            self._cap.release()
        self._cap = None

    def frames(self) -> Iterator[tuple[object, float]]:
        self.open()
        min_interval = 1.0 / self.sample_fps
        last_emit = 0.0
        reconnect_attempts = 0

        try:
            while True:
                if self._cap is None:
                    self.open()

                ret, frame_bgr = self._cap.read()
                if not ret:
                    if not self.is_stream:
                        LOGGER.info("Fim do arquivo de video. Frames capturados: %s", self._captured_frames)
                        break

                    reconnect_attempts += 1
                    if (
                        self.max_reconnect_attempts is not None
                        and reconnect_attempts > self.max_reconnect_attempts
                    ):
                        raise RuntimeError("Limite de tentativas de reconexao atingido.")

                    LOGGER.warning("Falha na leitura do stream. Tentando reconectar em %.1fs.", self.reconnect_delay)
                    self.release()
                    time.sleep(self.reconnect_delay)
                    continue

                reconnect_attempts = 0
                now = time.monotonic()
                if now - last_emit < min_interval:
                    continue

                last_emit = now
                self._captured_frames += 1
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                if self._captured_frames == 1 or self._captured_frames % 100 == 0:
                    LOGGER.info("Frames capturados: %s", self._captured_frames)
                yield frame_rgb, now
        finally:
            self.release()
