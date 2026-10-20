from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from api.services.camera_availability import CameraAvailabilitySampler, availability_timeline
from api.routers.insights import get_camera_availability


class AvailabilityTimelineTests(TestCase):
    def setUp(self):
        self.end = datetime(2026, 10, 19, 15, tzinfo=UTC)
        self.start = self.end - timedelta(hours=24)

    def check(self, at, status="online"):
        return SimpleNamespace(checked_at=at, status=status)

    def timeline(self, *checks):
        return availability_timeline(checks, self.start, self.end)

    def test_no_samples_never_implies_online_or_offline(self):
        result = self.timeline()
        self.assertIsNone(result["availability_percent"])
        self.assertEqual(result["coverage_percent"], 0)
        self.assertEqual(result["unknown_seconds"], 86400)
        self.assertEqual(result["current_status"], "unknown")

    def test_first_sample_does_not_backfill_history(self):
        result = self.timeline(self.check(self.end - timedelta(minutes=1)))
        self.assertEqual(result["online_seconds"], 60)
        self.assertEqual(result["unknown_seconds"], 86340)
        self.assertEqual(result["availability_percent"], 100)
        self.assertEqual([s["status"] for s in result["segments"]], ["unknown", "online"])

    def test_missing_heartbeats_become_unknown_after_three_minutes(self):
        result = self.timeline(self.check(self.start), self.check(self.start + timedelta(minutes=10), "offline"))
        self.assertEqual(result["online_seconds"], 180)
        self.assertEqual(result["offline_seconds"], 180)
        self.assertEqual(result["unknown_seconds"], 86040)
        self.assertEqual(result["availability_percent"], 50)
        self.assertEqual(result["current_status"], "unknown")

    def test_transition_is_exact_and_adjacent_checks_merge(self):
        result = self.timeline(
            self.check(self.end - timedelta(minutes=3)),
            self.check(self.end - timedelta(minutes=2)),
            self.check(self.end - timedelta(minutes=1), "offline"),
        )
        self.assertEqual(result["online_seconds"], 120)
        self.assertEqual(result["offline_seconds"], 60)
        self.assertEqual(result["availability_percent"], 66.7)
        self.assertEqual([s["status"] for s in result["segments"]], ["unknown", "online", "offline"])

    def test_check_before_window_only_covers_its_remaining_validity(self):
        result = self.timeline(self.check(self.start - timedelta(minutes=2)))
        self.assertEqual(result["online_seconds"], 60)
        self.assertEqual(result["segments"][0]["start_at"], self.start)

    def test_stale_and_future_samples_are_not_counted(self):
        result = self.timeline(self.check(self.start - timedelta(minutes=4)), self.check(self.end + timedelta(seconds=1)))
        self.assertEqual(result["online_seconds"], 0)
        self.assertEqual(result["unknown_seconds"], 86400)
        self.assertEqual(result["current_status"], "unknown")

    def test_segments_cover_window_without_overlaps(self):
        result = self.timeline(*(self.check(self.start + timedelta(seconds=i), "offline" if i % 2 else "online")
                                 for i in (0, 40, 400, 450, 86500)))
        self.assertEqual(sum(result[f"{s}_seconds"] for s in ("online", "offline", "unknown")), 86400)
        segments = result["segments"]
        self.assertEqual(segments[0]["start_at"], self.start)
        self.assertEqual(segments[-1]["end_at"], self.end)
        for left, right in zip(segments, segments[1:]):
            self.assertEqual(left["end_at"], right["start_at"])

    def test_status_expires_at_the_end_of_the_validity_window(self):
        result = self.timeline(self.check(self.end - timedelta(minutes=3)))
        self.assertEqual(result["online_seconds"], 180)
        self.assertEqual(result["current_status"], "unknown")


class AvailabilityAccessTests(TestCase):
    def test_membership_is_required_before_reading_history(self):
        db = MagicMock()
        db.get.return_value = SimpleNamespace(workspace_id="private-workspace")
        with patch("api.routers.insights.require_workspace_membership", side_effect=HTTPException(403, "Denied")):
            with self.assertRaises(HTTPException) as error:
                get_camera_availability(camera_id="camera", db=db, current_user=SimpleNamespace(id="outsider"))
        self.assertEqual(error.exception.status_code, 403)
        db.scalars.assert_not_called()

    def test_missing_migration_returns_clear_error(self):
        db = MagicMock()
        db.get.return_value = SimpleNamespace(workspace_id="workspace")
        with patch("api.routers.insights.require_workspace_membership"), patch("api.routers.insights.inspect") as inspector:
            inspector.return_value.has_table.return_value = False
            with self.assertRaises(HTTPException) as error:
                get_camera_availability(camera_id="camera", db=db, current_user=SimpleNamespace(id="member"))
        self.assertEqual(error.exception.status_code, 503)
        db.scalars.assert_not_called()

    def test_webcam_without_an_agent_is_unknown_even_if_saved_status_is_online(self):
        app = SimpleNamespace(state=SimpleNamespace())
        sampler = CameraAvailabilitySampler(app)
        camera = SimpleNamespace(id="camera", metadata_json={"protocol": "local-agent-webcam"}, status="online")
        online, _ = sampler._probe(camera)
        self.assertIsNone(online)

    def test_missing_migration_does_not_probe_or_write(self):
        sampler = CameraAvailabilitySampler(SimpleNamespace())
        with patch("api.services.camera_availability.SessionLocal") as session, patch("api.services.camera_availability.inspect") as inspector:
            inspector.return_value.has_table.return_value = False
            sampler.sample_once()
        db = session.return_value.__enter__.return_value
        db.scalars.assert_not_called()
        db.commit.assert_not_called()
