from __future__ import annotations

import base64
import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .frame_buffer import BufferedFrame


@dataclass(frozen=True)
class ClipExportResult:
    path: Path
    frame_count: int
    duration_seconds: float
    fps: float
    mime_type: str = "video/mp4"

    def to_payload(self) -> dict[str, object]:
        clip_bytes = self.path.read_bytes()
        return {
            "format": "base64",
            "mime_type": self.mime_type,
            "filename": self.path.name,
            "frame_count": self.frame_count,
            "duration_seconds": self.duration_seconds,
            "fps": self.fps,
            "size_bytes": len(clip_bytes),
            "content_base64": base64.b64encode(clip_bytes).decode("ascii"),
        }


class ClipExporter:
    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)

    def export_mp4(
        self,
        frames: list[BufferedFrame],
        fps: float,
        output_dir: str | Path | None = None,
        prefix: str = "fall_clip",
        max_fps: float = 8.0,
        max_dimension: int = 640,
    ) -> ClipExportResult | None:
        if not frames:
            return None
        if fps <= 0:
            raise ValueError("fps deve ser maior que zero.")
        if max_fps <= 0:
            raise ValueError("max_fps deve ser maior que zero.")
        if max_dimension <= 0:
            raise ValueError("max_dimension deve ser maior que zero.")

        destination_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
        destination_dir.mkdir(parents=True, exist_ok=True)
        output_path = destination_dir / f"{prefix}_{uuid.uuid4().hex}.mp4"

        export_frames = self._limit_fps(frames, max_fps=max_fps)
        playback_fps = min(
            max_fps,
            self._playback_fps(export_frames, fallback_fps=min(fps, max_fps)),
        )
        first_frame = export_frames[0].frame
        source_height, source_width = first_frame.shape[:2]
        width, height = self._output_size(source_width, source_height, max_dimension=max_dimension)
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            playback_fps,
            (width, height),
        )
        if not writer.isOpened():
            self.logger.error("Nao foi possivel abrir o VideoWriter para %s", output_path)
            return None

        written_frames = 0
        try:
            for item in export_frames:
                frame = item.frame
                if frame.shape[:2] != (source_height, source_width):
                    frame = cv2.resize(frame, (source_width, source_height))
                if (source_width, source_height) != (width, height):
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                written_frames += 1
        finally:
            writer.release()

        if written_frames == 0 or not output_path.exists():
            return None

        duration_seconds = written_frames / playback_fps
        return ClipExportResult(
            path=output_path,
            frame_count=written_frames,
            duration_seconds=duration_seconds,
            fps=playback_fps,
        )

    @staticmethod
    def _playback_fps(frames: list[BufferedFrame], *, fallback_fps: float) -> float:
        """Keep the exported MP4 duration aligned with the captured timeline."""
        if len(frames) < 2:
            return fallback_fps
        elapsed = frames[-1].timestamp - frames[0].timestamp
        if elapsed <= 0:
            return fallback_fps
        return len(frames) / elapsed

    @staticmethod
    def _limit_fps(frames: list[BufferedFrame], *, max_fps: float) -> list[BufferedFrame]:
        """Uniformly sample a clip so mobile clients receive a compact video."""
        if len(frames) < 2:
            return frames
        elapsed = frames[-1].timestamp - frames[0].timestamp
        if elapsed <= 0 or len(frames) / elapsed <= max_fps:
            return frames

        target_count = max(2, min(len(frames), int(elapsed * max_fps)))
        indices = np.linspace(0, len(frames) - 1, target_count).astype(int)
        return [frames[index] for index in indices]

    @staticmethod
    def _output_size(width: int, height: int, *, max_dimension: int) -> tuple[int, int]:
        largest_dimension = max(width, height)
        if largest_dimension <= max_dimension:
            return width, height

        scale = max_dimension / largest_dimension
        # Video encoders are more reliable with even dimensions.
        output_width = max(2, int(width * scale) // 2 * 2)
        output_height = max(2, int(height * scale) // 2 * 2)
        return output_width, output_height
