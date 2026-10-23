import queue
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from api.services.native_preview import NativePreview
from api.services.fall_monitor import CameraMonitorJob, CameraMonitorSpec
from fall_detection.config import FallDetectionConfig


class SharedPreviewTests(unittest.TestCase):
    def preview(self):
        preview = NativePreview.__new__(NativePreview)
        preview._process = MagicMock()
        preview._process.is_alive.return_value = True
        preview._queue = queue.Queue(maxsize=1)
        preview._interval = .125
        preview._last_submission = -float('inf')
        preview._max_width = 960
        return preview

    def test_preview_resizes_only_display_copy_and_preserves_aspect_ratio(self):
        preview = self.preview()
        original = np.full((1080, 1920, 3), 120, np.uint8)
        resized = preview.prepare_frame(original)
        self.assertEqual(resized.shape, (540, 960, 3))
        self.assertEqual(original.shape, (1080, 1920, 3))
        self.assertTrue(np.all(original == 120))

    def test_preview_rate_limit_skips_encoding_and_replaces_stale_frame(self):
        preview = self.preview()
        frame = np.zeros((20, 20, 3), np.uint8)
        with patch('api.services.native_preview.time.monotonic') as clock:
            with patch('api.services.native_preview.cv2.imencode', wraps=cv2.imencode) as encode:
                clock.return_value = 1
                self.assertTrue(preview.submit(frame))
                old = preview._queue.queue[0]
                clock.return_value = 1.05
                self.assertFalse(preview.should_submit())
                self.assertFalse(preview.submit(frame))
                self.assertEqual(encode.call_count, 1)
                clock.return_value = 1.2
                self.assertTrue(preview.submit(frame + 200))
                self.assertEqual(encode.call_count, 2)
                self.assertNotEqual(preview._queue.queue[0], old)

    def test_both_layers_share_one_camera_worker_and_one_preview(self):
        config = FallDetectionConfig(checkpoint=Path('unused.pt'), num_frames=2, sample_fps=10,
                                     stride_seconds=.1, threshold=.9, buffer_seconds=2)
        spec = CameraMonitorSpec(camera_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
                                 name='Teste', source='fake', config=config, capture_fps=16,
                                 freeze_seconds=0, show_preview=True, alert_cooldown_seconds=60,
                                 signature=(), confrontation_config=config)
        provider = MagicMock()
        provider.predict_frames.return_value = {'predicted_class': 'sem_queda', 'fall_probability': .01,
                                                'confrontation_probability': .01}
        worker = MagicMock()
        def frames(**_kwargs):
            for i in range(30):
                yield np.zeros((40, 60, 3), np.uint8), 100 + i * .1
                time.sleep(.002)
        worker.frames.side_effect = frames
        preview = MagicMock()
        preview.is_alive = True
        preview.should_submit.return_value = True
        preview.prepare_frame.side_effect = lambda frame: frame
        job = CameraMonitorJob(spec, provider)
        job._update_camera_status = MagicMock()
        with patch('api.services.fall_monitor.CameraWorker', return_value=worker) as capture:
            with patch('api.services.fall_monitor.NativePreview', return_value=preview) as display:
                job._monitor_loop()
        capture.assert_called_once()
        display.assert_called_once_with('Teste', max_fps=8, max_width=960)
        kinds = {call.kwargs['detector'] for call in provider.predict_frames.call_args_list}
        self.assertEqual(kinds, {'fall', 'confrontation'})
        preview.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
