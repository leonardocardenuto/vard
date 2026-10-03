from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import torch

from api.services.fall_monitor import FallClassifierProvider
from fall_detection.confrontation_inference import ConfrontationClassifier
from fall_detection.confrontation_model import ConfrontationHead


class ConfrontationInferenceTests(unittest.TestCase):
    def checkpoint(self, path, class_names=None):
        head = ConfrontationHead(4, 3, 0.3)
        with torch.no_grad():
            for parameter in head.parameters():
                parameter.zero_()
            head[3].bias.copy_(torch.tensor([0.0, 2.0]))
        torch.save({"head_state_dict": head.state_dict(), "model_name": "test/backbone",
                    "class_names": class_names or ["nao_confronto", "confronto"], "input_dim": 4,
                    "hidden_dim": 3, "dropout": 0.3, "num_frames": 16,
                    "view_duration_seconds": 2.0, "head_architecture": "fall_mlp_relu",
                    "recommended_threshold": 0.7}, path)

    @patch("fall_detection.confrontation_inference.AutoModel.from_pretrained")
    @patch("fall_detection.confrontation_inference.AutoVideoProcessor.from_pretrained")
    def test_training_head_pooling_and_semantic_class_order(self, processor_factory, model_factory):
        model = MagicMock()
        model.config.hidden_size = 4
        model.to.return_value = model
        model.return_value = SimpleNamespace(last_hidden_state=torch.arange(24).reshape(1, 6, 4).float())
        model_factory.return_value = model
        processor_factory.return_value.return_value = {"pixel_values_videos": torch.zeros(1, 16, 3, 2, 2)}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "head.pt"
            self.checkpoint(path)
            classifier = ConfrontationClassifier(path, device="cpu")
            captured = []
            classifier.head.register_forward_pre_hook(lambda module, args: captured.append(args[0]))
            frames = [np.zeros((2, 2, 3), dtype=np.uint8)] * 16
            result = classifier.predict_frames(frames)
            self.assertEqual(result["predicted_class"], "confronto")
            self.assertAlmostEqual(result["confrontation_probability"], 0.880797, places=5)
            self.assertNotIn("fall_probability", result)
            torch.testing.assert_close(captured[0], model.return_value.last_hidden_state.mean(dim=1))
            self.assertEqual(classifier.sample_fps, 7.5)
            self.assertEqual(classifier.recommended_threshold, 0.7)
            with self.assertRaisesRegex(ValueError, "16 frames"):
                classifier.predict_frames([])
            with self.assertRaisesRegex(ValueError, "Janela"):
                classifier.predict_video_windows("unused.mp4", sample_fps=6)
            self.checkpoint(path, ["confronto", "nao_confronto"])
            reverse = ConfrontationClassifier(path, device="cpu")
            self.assertAlmostEqual(reverse.predict_frames(frames)["confrontation_probability"], 0.119203, places=5)

    def test_incompatible_checkpoint_is_rejected_before_backbone_load(self):
        with tempfile.TemporaryDirectory() as directory, patch("fall_detection.confrontation_inference.AutoModel.from_pretrained") as load:
            path = Path(directory) / "head.pt"
            torch.save({"head_state_dict": {}}, path)
            with self.assertRaisesRegex(ValueError, "metadados"):
                ConfrontationClassifier(path, device="cpu")
            self.checkpoint(path, ["sem_arma", "armado"])
            with self.assertRaisesRegex(ValueError, "Classes"):
                ConfrontationClassifier(path, device="cpu")
            load.assert_not_called()

    def test_provider_routes_and_caches_confrontation_and_checks_window(self):
        provider = FallClassifierProvider("fall.pt", "cpu")
        with patch("fall_detection.confrontation_inference.ConfrontationClassifier") as factory:
            factory.return_value.sample_fps = 7.5
            provider.predict_frames([], checkpoint="confrontation.pt", detector="confrontation", sample_fps=7.5)
            provider.predict_frames([], checkpoint="confrontation.pt", detector="confrontation", sample_fps=7.5)
            factory.assert_called_once_with(Path("confrontation.pt"), device="cpu")
            with self.assertRaisesRegex(ValueError, "sample_fps"):
                provider.predict_frames([], checkpoint="confrontation.pt", detector="confrontation", sample_fps=6)
            self.assertEqual(factory.return_value.predict_frames.call_count, 2)

    def test_video_file_uses_training_duration_and_rejects_short_or_long_windows(self):
        classifier = object.__new__(ConfrontationClassifier)
        classifier.num_frames = 16
        classifier.view_duration_seconds = 2.0
        cap = MagicMock()
        cap.get.side_effect = [30, 180, 30, 180, 30, 30]
        with tempfile.TemporaryDirectory() as directory, \
             patch("fall_detection.confrontation_inference.cv2.VideoCapture", return_value=cap), \
             patch("fall_detection.inference.FallClassifier.predict_video_file") as predict:
            path = Path(directory) / "video.mp4"
            path.touch()
            classifier.predict_video_file(path)
            predict.assert_called_once_with(path, num_frames=16, start_frame=0, end_frame=59)
            with self.assertRaisesRegex(ValueError, "Janela"):
                classifier.predict_video_file(path, end_frame=179)
            with self.assertRaisesRegex(ValueError, "Janela"):
                classifier.predict_video_file(path)


if __name__ == "__main__":
    unittest.main()
