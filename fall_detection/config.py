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

    def __post_init__(self):
        if self.num_frames < 2 or self.sample_fps <= 0 or self.stride_seconds < 0:
            raise ValueError("num_frames >= 2, sample_fps positivo e stride_seconds >= 0 sao obrigatorios.")
        if not 0 <= self.threshold <= 1 or self.smoothing_window < 1 or self.min_consecutive_hits < 1:
            raise ValueError("Parametros de confirmacao temporal invalidos.")
        if self.buffer_seconds < (self.num_frames - 1) / self.sample_fps:
            raise ValueError("buffer_seconds precisa cobrir toda a janela de inferencia.")

    @property
    def buffer_max_frames(self) -> int:
        return max(self.num_frames, int(self.buffer_seconds * self.sample_fps) + self.num_frames)
