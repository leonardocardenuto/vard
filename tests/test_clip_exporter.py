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

    def test_limits_resolution_and_fps_for_mobile_playback(self):
        frames = [
            BufferedFrame(frame=np.zeros((1080, 1920, 3), dtype=np.uint8), timestamp=100.0 + index / 30)
            for index in range(61)
        ]
        with tempfile.TemporaryDirectory() as directory:
            result = ClipExporter().export_mp4(frames, fps=30.0, output_dir=directory)

            self.assertIsNotNone(result)
            self.assertLessEqual(result.fps, 8.0)
            self.assertLess(result.frame_count, len(frames))

            video = cv2.VideoCapture(str(result.path))
            try:
                self.assertEqual(video.get(cv2.CAP_PROP_FRAME_WIDTH), 640)
                self.assertEqual(video.get(cv2.CAP_PROP_FRAME_HEIGHT), 360)
                self.assertLessEqual(video.get(cv2.CAP_PROP_FPS), 8.0)
            finally:
                video.release()


if __name__ == "__main__":
    unittest.main()
