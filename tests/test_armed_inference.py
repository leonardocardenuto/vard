from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import torch

from api.services.fall_monitor import FallClassifierProvider
from fall_detection.armed_inference import ArmedClassifier, ArmedClassifierHead


class ArmedInferenceTests(unittest.TestCase):
    def checkpoint(self, path, class_names=None):
        head = ArmedClassifierHead(4, 3, 0.5)
        with torch.no_grad():
            for parameter in head.parameters():
                parameter.zero_()
            head.network[4].bias.copy_(torch.tensor([0.0, 2.0]))
        torch.save({"head_state_dict": head.state_dict(), "model_name": "test/backbone",
                    "class_names": class_names or ["sem_arma", "armado"], "input_dim": 4,
                    "hidden_dim": 3, "dropout": 0.5, "num_frames": 16,
                    "view_duration_seconds": 3.0}, path)

    @patch("fall_detection.armed_inference.AutoModel.from_pretrained")
    @patch("fall_detection.armed_inference.AutoVideoProcessor.from_pretrained")
    def test_head_checkpoint_pooling_and_class_order(self, processor_factory, model_factory):
        model = MagicMock()
        model.config.hidden_size = 4
        model.to.return_value = model
        model.return_value = SimpleNamespace(last_hidden_state=torch.arange(24).reshape(1, 6, 4).float())
        model_factory.return_value = model
        processor_factory.return_value.return_value = {"pixel_values_videos": torch.zeros(1, 16, 3, 2, 2)}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "head.pt"
            self.checkpoint(path)
            classifier = ArmedClassifier(path, device="cpu")
            captured = []
            classifier.head.register_forward_pre_hook(lambda module, args: captured.append(args[0]))
            result = classifier.predict_frames([np.zeros((2, 2, 3), dtype=np.uint8)] * 16)
            self.assertEqual(result["predicted_class"], "armado")
            self.assertAlmostEqual(result["armed_probability"], 0.880797, places=5)
            self.assertNotIn("fall_probability", result)
            torch.testing.assert_close(captured[0], model.return_value.last_hidden_state.mean(dim=1))
            self.assertEqual(classifier.sample_fps, 5)
            self.assertFalse(classifier.head.training)
            with self.assertRaisesRegex(ValueError, "16 frames"):
                classifier.predict_frames([])
            self.checkpoint(path, ["armado", "sem_arma"])
            reversed_classifier = ArmedClassifier(path, device="cpu")
            result = reversed_classifier.predict_frames([np.zeros((2, 2, 3), dtype=np.uint8)] * 16)
            self.assertAlmostEqual(result["armed_probability"], 0.119203, places=5)

    def test_invalid_checkpoint_rejected_before_loading_backbone(self):
        with tempfile.TemporaryDirectory() as directory, patch("fall_detection.armed_inference.AutoModel.from_pretrained") as load:
            path = Path(directory) / "head.pt"
            torch.save({"head_state_dict": {}}, path)
            with self.assertRaisesRegex(ValueError, "metadados"):
                ArmedClassifier(path, device="cpu")
            self.checkpoint(path, ["sem_queda", "queda"])
            with self.assertRaisesRegex(ValueError, "Classes"):
                ArmedClassifier(path, device="cpu")
            load.assert_not_called()

    def test_provider_refuses_temporal_window_different_from_training(self):
        provider = FallClassifierProvider("fall.pt", "cpu")
        classifier = MagicMock(sample_fps=5.0)
        with patch.object(provider, "_get_classifier", return_value=classifier):
            with self.assertRaisesRegex(ValueError, "sample_fps"):
                provider.predict_frames([], detector="armed", sample_fps=6)
            classifier.predict_frames.assert_not_called()


if __name__ == "__main__":
    unittest.main()
