from __future__ import annotations

import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import numpy as np

from api.services.fall_monitor import CameraMonitorJob, CameraMonitorSpec
from fall_detection import FallDetectionConfig


class _ImmediateFallClassifier:
    def predict_frames(self, _frames, **_kwargs):
        return {
            "predicted_class": "queda",
            "fall_probability": 0.99,
            "probabilities": {"queda": 0.99, "sem_queda": 0.01},
        }


class _TimedFrames:
    """Camera fake that behaves like a small live stream."""

    def __init__(self, *_args, **_kwargs):
        pass

    def frames(self, *, stop_event, pause_event):
        for index in range(80):
            if stop_event.is_set():
                return
            yield np.full((12, 16, 3), index, dtype=np.uint8), time.monotonic()
            time.sleep(0.025)


class FallClipRollTest(unittest.TestCase):
    def test_saved_clip_contains_context_before_and_after_detection(self):
        config = FallDetectionConfig(
            checkpoint=Path("unused.pkl"),
            num_frames=2,
            sample_fps=40.0,
            stride_seconds=0.0,
            threshold=0.5,
            smoothing_window=1,
            min_consecutive_hits=1,
            buffer_seconds=1.0,
        )
        spec = CameraMonitorSpec(
            camera_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
            name="Câmera teste",
            source="fake",
            config=config,
            capture_fps=40.0,
            clip_pre_seconds=0.05,
            clip_post_seconds=0.075,
            freeze_seconds=0.0,
            show_preview=False,
            alert_cooldown_seconds=60.0,
            signature=(),
        )
        job = CameraMonitorJob(spec, _ImmediateFallClassifier())
        saved: dict[str, object] = {}

        def capture_notification(*, clip_frames, clip_fps, **_kwargs):
            saved["frames"] = list(clip_frames)
            saved["fps"] = clip_fps
            job._stop_event.set()

        job._update_camera_status = lambda *_args, **_kwargs: None
        job._create_notification = capture_notification

        with patch("api.services.fall_monitor.CameraWorker", _TimedFrames):
            job.start()
            job._thread.join(timeout=5)

        self.assertFalse(job.is_alive(), "O monitor simulado deveria encerrar após salvar o clipe")
        frames = saved["frames"]
        self.assertGreaterEqual(len(frames), 5)
        self.assertGreaterEqual(frames[-1].timestamp - frames[0].timestamp, 0.10)
        self.assertEqual(saved["fps"], 40.0)


if __name__ == "__main__":
    unittest.main()
