from .camera_worker import CameraWorker
from .config import FallDetectionConfig
from .frame_buffer import FrameBuffer
from .temporal_smoother import TemporalSmoother

__all__ = [
    "CameraWorker",
    "FallClassifier",
    "FallDetectionConfig",
    "FrameBuffer",
    "TemporalSmoother",
]


def __getattr__(name: str):
    if name == "FallClassifier":
        from .inference import FallClassifier

        return FallClassifier
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
