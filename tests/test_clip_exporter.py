from __future__ import annotations

import tempfile
import unittest

import cv2
import numpy as np

from fall_detection.clip_exporter import ClipExporter
from fall_detection.frame_buffer import BufferedFrame


class ClipExporterTests(unittest.TestCase):
    def test_playback_duration_tracks_captured_frame_timestamps(self):
        frames = [
            BufferedFrame(frame=np.zeros((12, 16, 3), dtype=np.uint8), timestamp=100.0 + index * 0.5)
            for index in range(4)
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = ClipExporter().export_mp4(frames, fps=30.0, output_dir=directory)

            self.assertIsNotNone(result)
            self.assertAlmostEqual(result.fps, 4 / 1.5)
            self.assertAlmostEqual(result.duration_seconds, 1.5)
            self.assertTrue(result.path.exists())

            video = cv2.VideoCapture(str(result.path))
            try:
                self.assertAlmostEqual(video.get(cv2.CAP_PROP_FPS), 4 / 1.5, places=2)
                self.assertAlmostEqual(
                    video.get(cv2.CAP_PROP_FRAME_COUNT) / video.get(cv2.CAP_PROP_FPS), 1.5, places=2
                )
            finally:
                video.release()


if __name__ == "__main__":
    unittest.main()
