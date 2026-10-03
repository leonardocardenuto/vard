from __future__ import annotations

import unittest
import uuid
from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from api.core.config import Settings
from api.services.fall_monitor import CameraMonitorJob, CameraMonitorSpec, CameraMonitorSupervisor
from api.services.notifications import (create_armed_person_detected_notification, create_fall_detected_notification,
                                        create_confrontation_detected_notification)
from fall_detection.config import FallDetectionConfig
from fall_detection.frame_buffer import FrameBuffer


class ImmediateExecutor:
    """Deterministic scheduler for routing tests; the live clip test uses threads."""
    def __init__(self, **kwargs):
        pass

    def submit(self, fn, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future

    def shutdown(self, **kwargs):
        pass


class DetectionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.config = FallDetectionConfig(Path("fall.pt"), num_frames=2, sample_fps=1,
                                         smoothing_window=5, min_consecutive_hits=2)
        self.spec = CameraMonitorSpec(
            camera_id=uuid.uuid4(), workspace_id=uuid.uuid4(), name="Sala",
            source="rtsp://user:secret@camera/live", config=self.config,
            capture_fps=None, freeze_seconds=300, show_preview=False,
            alert_cooldown_seconds=60, signature=(), armed_config=self.config,
            armed_alert_cooldown_seconds=60,
        )
        self.provider = MagicMock()
        self.provider.predict_frames.side_effect = lambda frames, **kwargs: {
            "predicted_class": "armado" if kwargs["detector"] == "armed" else "queda",
            "fall_probability": 0.95, "armed_probability": 0.95,
            "probabilities": {"armado": 0.95, "sem_arma": 0.05},
        }
        self.job = CameraMonitorJob(self.spec, self.provider)
        self.buffer = FrameBuffer(300)
        for timestamp in range(101):
            self.buffer.append(np.zeros((2, 2, 3), dtype=np.uint8), float(timestamp))

    def test_simultaneous_alerts_have_independent_freeze_and_cooldown(self):
        fall, armed = self.job._detection_layers()
        with patch.object(self.job, "_create_notification") as notify, patch("api.services.fall_monitor.time.monotonic", return_value=2):
            for timestamp in (1, 2, 3):
                for layer in (fall, armed):
                    self.job._process_layer(layer, self.buffer, timestamp)
            self.assertEqual(notify.call_count, 2)
            self.assertEqual(fall.inference_count, 2)
            self.assertEqual(armed.inference_count, 3)
            self.job._process_layer(armed, self.buffer, 62)
            self.assertEqual(notify.call_count, 3)
            self.assertEqual(fall.last_alert_at, 2)
            self.assertEqual(armed.last_alert_at, 62)

    def test_single_positive_and_normal_windows_do_not_alert(self):
        layer = self.job._detection_layers()[1]
        with patch.object(self.job, "_create_notification") as notify:
            self.job._process_layer(layer, self.buffer, 1)
            self.provider.predict_frames.side_effect = lambda *a, **kw: {
                "predicted_class": "sem_arma", "armed_probability": 0.05,
            }
            for timestamp in range(2, 8):
                self.job._process_layer(layer, self.buffer, timestamp)
            notify.assert_not_called()
            self.assertEqual(layer.smoothing.consecutive_hits, 0)

    def test_persistence_failure_retries_without_consuming_cooldown(self):
        layer = self.job._detection_layers()[1]
        with patch.object(self.job, "_create_notification", side_effect=[RuntimeError("db unavailable"), None]) as notify:
            for timestamp in (1, 2, 3):
                self.job._process_layer(layer, self.buffer, timestamp)
            self.assertEqual(notify.call_count, 2)
            self.assertEqual(layer.last_alert_at, 3)

    def test_freeze_expires_and_requires_fresh_confirmation(self):
        layer = self.job._detection_layers()[0]
        layer.freeze_seconds = 3
        with patch.object(self.job, "_create_notification") as notify, patch("api.services.fall_monitor.time.monotonic", return_value=2):
            for timestamp in (1, 2, 3, 4, 5):
                self.job._process_layer(layer, self.buffer, timestamp)
            self.assertEqual(layer.inference_count, 3)
            self.assertEqual(layer.smoothing.consecutive_hits, 1)
            self.assertEqual(notify.call_count, 1)

    def test_armed_payload_is_routed_and_credentials_are_masked(self):
        layer = self.job._detection_layers()[1]
        with patch("api.services.fall_monitor.SessionLocal"), patch("api.services.fall_monitor.create_armed_person_detected_notification") as armed, patch("api.services.fall_monitor.create_fall_detected_notification") as fall:
            for timestamp in (1, 2):
                self.job._process_layer(layer, self.buffer, timestamp)
            fall.assert_not_called()
            data = armed.call_args.kwargs
            self.assertEqual(data["workspace_id"], self.spec.workspace_id)
            self.assertEqual(data["camera_id"], self.spec.camera_id)
            self.assertEqual(data["payload"]["armed_probability"], 0.95)
            self.assertEqual(data["payload"]["confidence"], 95)
            self.assertNotIn("fall_probability", data["payload"])
            self.assertNotIn("secret", data["payload"]["source"])

    def test_model_failure_does_not_stop_other_layer(self):
        worker = MagicMock()
        worker.frames.return_value = [(np.zeros((2, 2, 3), dtype=np.uint8), float(t)) for t in range(5)]
        original_predict = self.provider.predict_frames.side_effect

        def predict(frames, **kwargs):
            if kwargs["detector"] == "fall":
                raise RuntimeError("fall checkpoint unavailable")
            return original_predict(frames, **kwargs)

        self.provider.predict_frames.side_effect = predict
        with patch("api.services.fall_monitor.ThreadPoolExecutor", ImmediateExecutor), patch("api.services.fall_monitor.CameraWorker", return_value=worker), patch.object(self.job, "_update_camera_status"), patch.object(self.job, "_create_notification") as notify:
            self.job._monitor_loop()
            self.assertIsNone(self.job.failed_at)
            self.assertEqual(notify.call_count, 1)
            self.assertEqual(notify.call_args.kwargs["layer"].kind, "armed")
            worker.release.assert_called_once()

    def test_confrontation_routes_payload_with_its_own_cooldown(self):
        spec = replace(self.spec, confrontation_config=self.config)
        job = CameraMonitorJob(spec, self.provider)
        original = self.provider.predict_frames.side_effect
        self.provider.predict_frames.side_effect = lambda frames, **kw: (
            {"predicted_class": "confronto", "confrontation_probability": 0.95,
             "probabilities": {"confronto": 0.95, "nao_confronto": 0.05}}
            if kw["detector"] == "confrontation" else original(frames, **kw)
        )
        fall, armed, confrontation = job._detection_layers()
        with patch("api.services.fall_monitor.SessionLocal"), \
             patch("api.services.fall_events.record_fall_event") as record_event, \
             patch("api.services.fall_monitor.create_fall_detected_notification") as fall_notify, \
             patch("api.services.fall_monitor.create_armed_person_detected_notification") as armed_notify, \
             patch("api.services.fall_monitor.create_confrontation_detected_notification") as confrontation_notify, \
             patch("api.services.fall_monitor.time.monotonic", return_value=2):
            for timestamp in (1, 2, 3):
                for layer in (fall, armed, confrontation):
                    job._process_layer(layer, self.buffer, timestamp)
            self.assertEqual(fall_notify.call_count, 1)
            record_event.assert_called_once()
            self.assertEqual(record_event.return_value.notification_id, fall_notify.return_value.id)
            self.assertEqual(armed_notify.call_count, 1)
            self.assertEqual(confrontation_notify.call_count, 1)
            payload = confrontation_notify.call_args.kwargs["payload"]
            self.assertEqual(payload["detector"], "confrontation")
            self.assertEqual(payload["confrontation_probability"], 0.95)
            self.assertEqual(payload["confidence"], 95)
            self.assertNotIn("fall_probability", payload)
            self.assertNotIn("secret", payload["source"])
            job._process_layer(confrontation, self.buffer, 62)
            self.assertEqual(confrontation_notify.call_count, 2)
            self.assertEqual(armed.last_alert_at, 2)
            self.assertEqual(fall.inference_count, 2)

    def test_normal_confrontation_window_does_not_notify(self):
        job = CameraMonitorJob(replace(self.spec, confrontation_config=self.config), self.provider)
        layer = job._detection_layers()[2]
        self.provider.predict_frames.side_effect = None
        self.provider.predict_frames.return_value = {"predicted_class": "nao_confronto", "confrontation_probability": 0.05}
        with patch.object(job, "_create_notification") as notify:
            for timestamp in range(1, 8):
                job._process_layer(layer, self.buffer, timestamp)
            notify.assert_not_called()

    def test_fall_post_roll_keeps_other_layer_active_and_preserves_snapshot(self):
        spec = replace(self.spec, clip_pre_seconds=1, clip_post_seconds=2)
        job = CameraMonitorJob(spec, self.provider)
        fall, armed = job._detection_layers()
        buffer = FrameBuffer(100)
        with patch.object(job, "_create_notification") as notify, \
             patch("api.services.fall_monitor.time.monotonic", return_value=4):
            for timestamp in range(5):
                frame = np.zeros((12, 16, 3), dtype=np.uint8)
                buffer.append(frame, float(timestamp))
                job._latest_frame = frame
                job._process_layer(fall, buffer, timestamp)
                job._process_layer(armed, buffer, timestamp)
                if timestamp == 2:
                    self.assertIsNotNone(fall.pending_alert)
                    self.assertEqual(notify.call_count, 1)
                    self.assertEqual(notify.call_args.kwargs["layer"].kind, "armed")
            self.assertEqual(notify.call_count, 2)
            self.assertEqual(notify.call_args.kwargs["layer"].kind, "fall")
            self.assertEqual([item.timestamp for item in notify.call_args.kwargs["clip_frames"]], [1, 2, 3, 4])
            self.assertEqual(armed.inference_count, 4)
            self.assertIsNone(fall.pending_alert)
            self.assertTrue(job.snapshot_jpeg().startswith(b"\xff\xd8"))


class MonitorConfigurationTests(unittest.TestCase):
    def setUp(self):
        settings = Settings(_env_file=None, DATABASE_URL="postgresql://test:test@localhost/test",
                            JWT_SECRET_KEY="test", ARMED_MONITOR_ENABLED=True)
        self.supervisor = CameraMonitorSupervisor(settings)
        self.camera = SimpleNamespace(id=uuid.uuid4(), workspace_id=uuid.uuid4(), name="Sala",
                                      stream_url="rtsp://camera", metadata_json={})

    def test_armed_layer_inherits_existing_camera_opt_in(self):
        self.camera.metadata_json = {"fall_monitor": {"enabled": True, "freeze_seconds": 0,
                                                     "alert_cooldown_seconds": 0, "threshold": 0}}
        spec = self.supervisor._spec_from_camera(self.camera)
        self.assertIsNotNone(spec.armed_config)
        self.assertEqual(spec.armed_config.sample_fps, 5)
        self.assertEqual(spec.freeze_seconds, 0)
        self.assertEqual(spec.alert_cooldown_seconds, 0)
        self.assertEqual(spec.config.threshold, 0)

    def test_armed_only_and_explicit_disable(self):
        self.camera.metadata_json = {"armed_monitor": {"enabled": True}}
        spec = self.supervisor._spec_from_camera(self.camera)
        self.assertFalse(spec.fall_enabled)
        self.assertEqual([layer.kind for layer in CameraMonitorJob(spec, MagicMock())._detection_layers()], ["armed"])
        self.camera.metadata_json = {"fall_monitor": {"enabled": True}, "armed_monitor": {"enabled": False}}
        self.assertIsNone(self.supervisor._spec_from_camera(self.camera).armed_config)

    def test_unconfigured_camera_not_monitored_and_changes_restart_job(self):
        self.assertIsNone(self.supervisor._spec_from_camera(self.camera))
        self.camera.metadata_json = {"armed_monitor": {"enabled": True}}
        first = self.supervisor._spec_from_camera(self.camera)
        self.camera.metadata_json["armed_monitor"]["threshold"] = 0.9
        second = self.supervisor._spec_from_camera(self.camera)
        self.assertNotEqual(first.signature, second.signature)

    def test_confrontation_only_inheritance_disable_and_reconfigure(self):
        self.camera.metadata_json = {"confrontation_monitor": {"enabled": True, "capture_fps": 15}}
        first = self.supervisor._spec_from_camera(self.camera)
        self.assertFalse(first.fall_enabled)
        self.assertIsNone(first.armed_config)
        self.assertEqual(first.capture_fps, 15)
        self.assertEqual(first.confrontation_config.sample_fps, 7.5)
        self.assertEqual([layer.kind for layer in CameraMonitorJob(first, MagicMock())._detection_layers()], ["confrontation"])
        self.camera.metadata_json["confrontation_monitor"]["threshold"] = 0.99
        self.assertNotEqual(first.signature, self.supervisor._spec_from_camera(self.camera).signature)
        self.supervisor.settings.confrontation_monitor_enabled = True
        self.camera.metadata_json = {"fall_monitor": {"enabled": True}}
        self.assertIsNotNone(self.supervisor._spec_from_camera(self.camera).confrontation_config)
        self.camera.metadata_json["confrontation_monitor"] = {"enabled": False}
        self.assertIsNone(self.supervisor._spec_from_camera(self.camera).confrontation_config)


class NotificationTests(unittest.TestCase):
    @patch("api.services.notifications.send_push_to_subscription_ids")
    def test_persist_then_push_both_event_types_to_workspace_members(self, push):
        for create, event_type in ((create_armed_person_detected_notification, "armed_person_detected"),
                                   (create_fall_detected_notification, "fall_detected"),
                                   (create_confrontation_detected_notification, "confrontation_detected")):
            db = MagicMock()
            db.scalars.return_value.all.return_value = ["subscription-1"]
            db.refresh.side_effect = lambda notification: setattr(notification, "id", uuid.uuid4())
            workspace_id, camera_id = uuid.uuid4(), uuid.uuid4()
            notification = create(db, workspace_id=workspace_id, camera_id=camera_id, payload={"confidence": 95})
            db.commit.assert_called_once()
            self.assertEqual(notification.notification_type, event_type)
            self.assertEqual(notification.severity, "critical")
            self.assertEqual(push.call_args.args[0], ["subscription-1"])
            self.assertEqual(push.call_args.kwargs["data"]["notification_type"], event_type)
            self.assertEqual(push.call_args.kwargs["data"]["workspace_id"], str(workspace_id))
            query = db.scalars.call_args.args[0].compile(compile_kwargs={"literal_binds": True})
            self.assertIn("workspace_members.status = 'active'", str(query))
            self.assertIn(workspace_id.hex, str(query).replace("-", ""))


if __name__ == "__main__":
    unittest.main()
