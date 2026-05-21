from __future__ import annotations

import base64
import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

import cv2

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
    ) -> ClipExportResult | None:
        if not frames:
            return None
        if fps <= 0:
            raise ValueError("fps deve ser maior que zero.")

        destination_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir())
        destination_dir.mkdir(parents=True, exist_ok=True)
        output_path = destination_dir / f"{prefix}_{uuid.uuid4().hex}.mp4"

        first_frame = frames[0].frame
        height, width = first_frame.shape[:2]
        writer = cv2.VideoWriter(
            str(output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )
        if not writer.isOpened():
            self.logger.error("Nao foi possivel abrir o VideoWriter para %s", output_path)
            return None

        written_frames = 0
        try:
            for item in frames:
                frame = item.frame
                if frame.shape[:2] != (height, width):
                    frame = cv2.resize(frame, (width, height))
                writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                written_frames += 1
        finally:
            writer.release()

        if written_frames == 0 or not output_path.exists():
            return None

        duration_seconds = written_frames / fps
        return ClipExportResult(
            path=output_path,
            frame_count=written_frames,
            duration_seconds=duration_seconds,
            fps=fps,
        )
