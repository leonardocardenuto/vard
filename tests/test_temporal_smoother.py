import unittest
from pathlib import Path

from api.services.fall_monitor import DetectionLayer
from fall_detection.config import FallDetectionConfig
from fall_detection.temporal_smoother import TemporalSmoother


class TemporalSmootherTests(unittest.TestCase):
    def test_perfect_prediction_adds_two_to_existing_sequence(self):
        smoother = TemporalSmoother(.9, 5, 4)
        self.assertEqual(smoother.update(.95).consecutive_hits, 1)
        result = smoother.update(1.0)
        self.assertEqual(result.consecutive_hits, 3)
        self.assertFalse(result.alert)
        result = smoother.update(.96)
        self.assertEqual(result.consecutive_hits, 4)
        self.assertTrue(result.alert)

    def test_two_perfect_predictions_satisfy_four_hits(self):
        smoother = TemporalSmoother(.9, 5, 4)
        self.assertFalse(smoother.update(1).alert)
        self.assertTrue(smoother.update(1).alert)

    def test_double_hits_threshold_is_inclusive_and_uses_unrounded_score(self):
        for value, expected in ((.989999, 1), (.99, 2), (.9999520778656006, 2), (1.0, 2)):
            with self.subTest(probability=value):
                smoother = TemporalSmoother(.9, 5, 4)
                self.assertEqual(smoother.update(value).consecutive_hits, expected)

    def test_double_hits_still_require_detection_threshold(self):
        smoother = TemporalSmoother(.995, 5, 4)
        self.assertEqual(smoother.update(.99).consecutive_hits, 0)
        self.assertEqual(smoother.update(.999).consecutive_hits, 2)

    def test_low_probability_and_reset_clear_weighted_hits(self):
        smoother = TemporalSmoother(.9, 5, 4)
        smoother.update(1)
        self.assertEqual(smoother.update(.2).consecutive_hits, 0)
        self.assertEqual(smoother.update(1).consecutive_hits, 2)
        smoother.reset()
        self.assertEqual(smoother.update(.95).consecutive_hits, 1)

    def test_moving_average_remains_unweighted(self):
        smoother = TemporalSmoother(.8, 3, 99)
        smoother.update(.9)
        smoother.update(.9)
        result = smoother.update(1)
        self.assertAlmostEqual(result.moving_average, 2.8 / 3)
        self.assertTrue(result.alert)

    def test_only_fall_layer_gets_double_hits(self):
        config = FallDetectionConfig(checkpoint=Path('unused.pt'), threshold=.9,
                                     smoothing_window=5, min_consecutive_hits=4)
        for kind in ('fall', 'confrontation', 'armed'):
            with self.subTest(kind=kind):
                layer = DetectionLayer(kind, config, cooldown_seconds=60)
                self.assertEqual(layer.smoother.update(.99).consecutive_hits, 2 if kind == 'fall' else 1)


if __name__ == '__main__':
    unittest.main()
