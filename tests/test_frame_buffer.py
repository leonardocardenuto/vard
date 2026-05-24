from __future__ import annotations

import unittest

import numpy as np

from fall_detection.frame_buffer import FrameBuffer


class FrameBufferSamplingTests(unittest.TestCase):
    def test_dense_capture_preserves_sparse_window_shape(self):
        buffer = FrameBuffer(max_frames=300)

        for index in range(151):
            timestamp = index / 25.0
            frame = np.full((2, 2, 3), index, dtype=np.uint8)
            buffer.append(frame, timestamp)

        window = buffer.sample_window(num_frames=25, sample_fps=4.0, end_timestamp=6.0)

        self.assertEqual(len(window), 25)
        self.assertEqual(int(window[0][0, 0, 0]), 0)
        self.assertEqual(int(window[-1][0, 0, 0]), 150)


if __name__ == "__main__":
    unittest.main()
