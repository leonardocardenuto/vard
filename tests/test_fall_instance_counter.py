import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from fall_detection import FallDetectionConfig
from scripts.run_fall_detection import RuntimeState, _draw_preview, _inference_loop


class FallInstanceCounterTests(unittest.TestCase):
    def update(self, runtime, alert):
        return runtime.update_inference(
            prediction={}, moving_average=.9, consecutive_hits=2,
            alert=alert, inference_count=1, window_end_timestamp=1, window_frames=[])

    def test_sustained_alert_counts_once_and_new_instance_starts_at_zero(self):
        runtime = RuntimeState()
        self.assertEqual(runtime.snapshot()[1].fall_count, 0)
        self.assertTrue(self.update(runtime, True))
        self.assertFalse(self.update(runtime, True))
        self.assertFalse(self.update(runtime, True))
        self.assertEqual(runtime.snapshot()[1].fall_count, 1)
        self.assertFalse(self.update(runtime, False))
        self.assertTrue(self.update(runtime, True))
        self.assertEqual(runtime.snapshot()[1].fall_count, 2)
        self.assertEqual(RuntimeState().snapshot()[1].fall_count, 0)

    def test_freeze_preserves_total_and_does_not_recount_sustained_alert(self):
        runtime = RuntimeState()
        self.update(runtime, True)
        runtime.start_freeze(100)
        runtime.clear_freeze()
        self.assertFalse(self.update(runtime, True))
        self.assertEqual(runtime.snapshot()[1].fall_count, 1)

    def test_stream_counts_confirmed_alert_episodes(self):
        scores = iter([.1, .99, .99, .1, .99])
        classifier = MagicMock()
        def predict(_frames):
            score = next(scores)
            return {'predicted_class': 'queda' if score > .5 else 'sem_queda',
                    'fall_probability': score, 'probabilities': {'queda': score, 'sem_queda': 1-score}}
        classifier.predict_frames.side_effect = predict
        class Buffer:
            timestamp = 0
            def latest_timestamp(self):
                self.timestamp += 1
                return self.timestamp
            def sample_window_buffered(self, **kwargs):
                return [SimpleNamespace(frame=np.zeros((8, 8, 3), np.uint8)) for _ in range(2)]
            def __len__(self):
                return 2
        config = FallDetectionConfig(checkpoint=Path('unused.pt'), num_frames=2,
                                     sample_fps=2, stride_seconds=.1, threshold=.8,
                                     smoothing_window=1, min_consecutive_hits=1, buffer_seconds=2)
        runtime = RuntimeState()
        logger = MagicMock()
        args = SimpleNamespace(source='fake', save_fall_windows=False, freeze_seconds=0, max_inferences=5)
        count = _inference_loop(classifier, Buffer(), runtime, threading.Event(),
                                threading.Event(), config, args, logger)
        self.assertEqual(count, 5)
        self.assertEqual(runtime.snapshot()[1].fall_count, 2)
        counted = [call for call in logger.warning.call_args_list if call.args[0].startswith('QUEDA_CONTABILIZADA')]
        self.assertEqual([call.args[1] for call in counted], [1, 2])

    def test_preview_displays_instance_total(self):
        with patch('scripts.run_fall_detection.cv2.putText', wraps=__import__('cv2').putText) as put_text:
            _draw_preview(np.zeros((240, 640, 3), np.uint8), None, None, None, False, fall_count=7)
        self.assertIn('Quedas nesta instancia: 7', [call.args[1] for call in put_text.call_args_list])


if __name__ == '__main__':
    unittest.main()
