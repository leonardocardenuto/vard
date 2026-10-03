from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
import torch

from train_confrontation_classifier import Sample, VideoDataset, slice_videos, source_map, split_videos


class ConfrontationTrainingTests(unittest.TestCase):
    def test_source_clips_and_camera_views_stay_in_one_split(self):
        rows = [Sample(f"{group}-{camera}.mp4", "airtlab", group % 2,
                       f"event:{group}", f"event:{group}:cam{camera}")
                for group in range(40) for camera in (1, 2)]
        split = split_videos(rows, seed=42)
        for group in range(40):
            self.assertEqual(len({row.split for row in split if row.source_id == f"event:{group}"}), 1)
        for name in ("train", "validation", "test"):
            self.assertEqual({row.label for row in split if row.split == name}, {0, 1})

    def test_scfd_fight_and_normal_from_same_origin_are_grouped(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scfd").mkdir()
            (root / "scfd/videos.txt").write_text(
                "https://www.youtube.com/watch?v=example\nfi001 : 0-2\nnofi001 : 2-4\n", encoding="utf-8")
            mapping = source_map(root)
            self.assertEqual(mapping["fi001"], mapping["nofi001"])
            self.assertEqual(mapping["nofi062"], mapping["nofi091"])

    def test_slicing_drops_short_tail_and_preserves_split(self):
        video = Sample("example.mp4", "scfd", 1, "source", "video",
                       fps=30, total_frames=145, split="test")
        windows = slice_videos([video], 2)
        self.assertEqual([(row.start_frame, row.end_frame) for row in windows], [(0, 59), (60, 119)])
        self.assertTrue(all(row.split == "test" and row.source_id == "source" for row in windows))
        video.total_frames = 59
        self.assertEqual(len(slice_videos([video], 2)), 1)
        video.total_frames = 40
        self.assertEqual(slice_videos([video], 2), [])

    def test_sequential_decoder_returns_same_uniform_frames_as_seeking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.avi"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (32, 32))
            self.assertTrue(writer.isOpened())
            for index in range(90):
                writer.write(np.full((32, 32, 3), index * 2, dtype=np.uint8))
            writer.release()
            row = Sample(str(path), "test", 1, "source", "video", fps=30,
                         total_frames=90, start_frame=30, end_frame=89)
            processor = lambda frames, **kw: {"pixel_values_videos": torch.from_numpy(np.stack(frames))[None]}
            decoded = VideoDataset([row], processor, 16)[0].numpy()
            cap = cv2.VideoCapture(str(path))
            expected = []
            for index in np.linspace(30, 89, 16).astype(int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                ok, frame = cap.read()
                self.assertTrue(ok)
                expected.append(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            cap.release()
            np.testing.assert_array_equal(decoded, np.stack(expected))


if __name__ == "__main__":
    unittest.main()
