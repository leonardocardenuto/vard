from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FallDetectionConfig:
    checkpoint: Path
    num_frames: int = 16
    sample_fps: float = 6.0
    stride_seconds: float = 1.0
    threshold: float = 0.75
    smoothing_window: int = 5
    min_consecutive_hits: int = 2
    buffer_seconds: float = 8.0
    device: str | None = None

    @property
    def buffer_max_frames(self) -> int:
        return max(self.num_frames, int(self.buffer_seconds * self.sample_fps) + self.num_frames)
