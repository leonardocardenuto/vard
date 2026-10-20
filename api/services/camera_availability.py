"""Measured camera connectivity. Unobserved intervals remain unknown."""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import inspect, select

from api.core.config import get_settings
from api.db import SessionLocal
from api.models import Camera, CameraAvailabilityCheck

LOGGER = logging.getLogger(__name__)
CHECK_VALID_SECONDS = 180


def availability_timeline(checks, start: datetime, end: datetime) -> dict:
    """A check is valid for at most three minutes, never before it was observed."""
    segments = []
    cursor = start

    def append_segment(status, left, right):
        if right <= left:
            return
        if segments and segments[-1]["status"] == status and segments[-1]["end_at"] == left:
            segments[-1]["end_at"] = right
        else:
            segments.append({"status": status, "start_at": left, "end_at": right})

    ordered = sorted((check for check in checks if check.checked_at <= end), key=lambda c: c.checked_at)
    for index, check in enumerate(ordered):
        left = max(start, check.checked_at)
        right = min(end, check.checked_at + timedelta(seconds=CHECK_VALID_SECONDS))
        if index + 1 < len(ordered):
            right = min(right, ordered[index + 1].checked_at)
        if right <= left:
            continue
        append_segment("unknown", cursor, left)
        append_segment(check.status, left, right)
        cursor = right
    append_segment("unknown", cursor, end)

    seconds = {status: sum((s["end_at"] - s["start_at"]).total_seconds()
                          for s in segments if s["status"] == status)
               for status in ("online", "offline", "unknown")}
    measured = seconds["online"] + seconds["offline"]
    return {
        "start_at": start,
        "end_at": end,
        "segments": segments,
        "online_seconds": seconds["online"],
        "offline_seconds": seconds["offline"],
        "unknown_seconds": seconds["unknown"],
        "availability_percent": round(seconds["online"] / measured * 100, 1) if measured else None,
        "coverage_percent": round(measured / (end - start).total_seconds() * 100, 1),
        "last_checked_at": ordered[-1].checked_at if ordered else None,
        "current_status": (ordered[-1].status if ordered and
                           end - ordered[-1].checked_at < timedelta(seconds=CHECK_VALID_SECONDS)
                           else "unknown"),
    }


class CameraAvailabilitySampler:
    def __init__(self, app):
        self.app = app
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="camera-availability", daemon=True)
        self._missing_table_logged = False

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)

    def _probe(self, camera):
        supervisor = getattr(self.app.state, "fall_monitor_supervisor", None)
        if supervisor is not None:
            observed = supervisor.has_recent_frame(camera.id)
            if observed is not None:
                return observed, datetime.now(UTC)
        if (camera.metadata_json or {}).get("protocol") == "local-agent-webcam":
            # No access to the webcam agent: its saved status is not a measurement.
            return None, datetime.now(UTC)
        from api.routers.cameras import _camera_has_pong
        try:
            return _camera_has_pong(camera), datetime.now(UTC)
        except (ValueError, OSError):
            return False, datetime.now(UTC)

    def sample_once(self):
        with SessionLocal() as db:
            if not inspect(db.connection()).has_table("camera_availability_checks"):
                if not self._missing_table_logged:
                    LOGGER.warning("Disponibilidade: aplique sql/013_camera_availability_checks.sql para iniciar a coleta.")
                    self._missing_table_logged = True
                return
            cameras = list(db.scalars(select(Camera).where(Camera.is_active.is_(True))).all())
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="camera-probe") as pool:
            observations = list(pool.map(self._probe, cameras))
        with SessionLocal() as db:
            for camera, (online, checked_at) in zip(cameras, observations):
                if online is None:
                    continue
                current = db.get(Camera, camera.id)
                if current is None or not current.is_active or current.stream_url != camera.stream_url:
                    continue
                current.status = "online" if online else "offline"
                if online:
                    current.last_seen_at = checked_at
                db.add(CameraAvailabilityCheck(camera_id=camera.id, status=current.status, checked_at=checked_at))
            db.commit()

    def _run(self):
        while not self._stop.is_set():
            try:
                self.sample_once()
            except Exception:
                LOGGER.exception("Falha ao verificar disponibilidade das câmeras")
            self._stop.wait(get_settings().camera_availability_interval_seconds)
