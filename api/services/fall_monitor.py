from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
from sqlalchemy import select

from api.core.config import Settings, get_settings
from api.db import SessionLocal
from api.models import Camera
from api.services.notifications import create_fall_detected_notification
from api.services.native_preview import NativePreview
from fall_detection import CameraWorker, FallDetectionConfig, FrameBuffer, TemporalSmoother
from fall_detection.clip_exporter import ClipExporter

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraMonitorSpec:
    camera_id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    source: str
    config: FallDetectionConfig
    capture_fps: float | None
    clip_pre_seconds: float
    clip_post_seconds: float
    freeze_seconds: float
    show_preview: bool
    alert_cooldown_seconds: float
    signature: tuple[Any, ...]


class FallClassifierProvider:
    def __init__(self, checkpoint: str | Path, device: str | None):
        self.default_checkpoint = Path(checkpoint)
        self.default_device = device
        self._classifiers = {}
        self._load_lock = threading.Lock()
        self._predict_lock = threading.Lock()

    def predict_frames(self, frames: list, *, checkpoint: str | Path | None = None, device: str | None = None) -> dict:
        classifier = self._get_classifier(
            Path(checkpoint) if checkpoint is not None else self.default_checkpoint,
            device if device is not None else self.default_device,
        )
        with self._predict_lock:
            return classifier.predict_frames(frames)

    def _get_classifier(self, checkpoint: Path, device: str | None):
        key = (str(checkpoint), device)
        if key in self._classifiers:
            return self._classifiers[key]
        with self._load_lock:
            if key not in self._classifiers:
                from fall_detection import FallClassifier

                LOGGER.info(
                    "fall monitor classifier loading: checkpoint=%s device=%s",
                    checkpoint,
                    device or "auto",
                )
                self._classifiers[key] = FallClassifier(checkpoint, device=device)
        return self._classifiers[key]


class CameraMonitorJob:
    def __init__(self, spec: CameraMonitorSpec, classifier_provider: FallClassifierProvider):
        self.spec = spec
        self.classifier_provider = classifier_provider
        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name=f"fall-monitor-{spec.camera_id}",
            daemon=True,
        )
        self._running_lock = threading.Lock()
        self._running = False
        self._latest_frame_lock = threading.Lock()
        self._latest_frame = None
        self.failed_at: float | None = None

    def start(self):
        LOGGER.info(
            "fall monitor job enabled: camera_id=%s workspace_id=%s name=%s source=%s",
            self.spec.camera_id,
            self.spec.workspace_id,
            self.spec.name,
            _mask_source(self.spec.source),
        )
        self._thread.start()

    def stop(self, timeout: float = 5.0):
        self._stop_event.set()
        self._thread.join(timeout=timeout)
        LOGGER.info("fall monitor job stopped: camera_id=%s", self.spec.camera_id)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def snapshot_jpeg(self) -> bytes | None:
        with self._latest_frame_lock:
            if self._latest_frame is None:
                return None
            frame = self._latest_frame.copy()

        success, encoded = cv2.imencode(
            ".jpg",
            cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
            [int(cv2.IMWRITE_JPEG_QUALITY), 80],
        )
        return encoded.tobytes() if success else None

    def _run(self):
        with self._running_lock:
            if self._running:
                return
            self._running = True
        try:
            self._monitor_loop()
        finally:
            with self._running_lock:
                self._running = False

    def _monitor_loop(self):
        config = self.spec.config
        estimated_capture_fps = self.spec.capture_fps or max(config.sample_fps, 30.0)
        worker = CameraWorker(self.spec.source, sample_fps=self.spec.capture_fps)
        clip_capture_fps = self.spec.capture_fps or estimated_capture_fps
        buffer = FrameBuffer(
            max_frames=max(
                config.num_frames,
                int(max(config.buffer_seconds, self.spec.clip_pre_seconds) * estimated_capture_fps)
                + config.num_frames,
            )
        )
        smoother = TemporalSmoother(
            threshold=config.threshold,
            window_size=config.smoothing_window,
            min_consecutive_hits=config.min_consecutive_hits,
        )
        last_inference_at: float | None = None
        last_alert_at = -float("inf")
        freeze_until_monotonic: float | None = None
        pause_event = threading.Event()
        inference_count = 0
        skipped_windows = 0
        latest_prediction: dict | None = None
        latest_smoothing = None
        pending_alert: dict[str, Any] | None = None
        preview: NativePreview | None = None
        if self.spec.show_preview:
            try:
                preview = NativePreview(self.spec.name)
            except Exception as exc:
                LOGGER.warning(
                    "fall monitor preview unavailable: camera_id=%s camera=%s reason=%s",
                    self.spec.camera_id,
                    self.spec.name,
                    exc,
                )
        prediction_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="fall-inference")
        prediction_future: Future | None = None
        prediction_context = None

        def consume_completed_prediction():
            nonlocal last_alert_at, latest_prediction, latest_smoothing, pending_alert
            nonlocal last_inference_at, prediction_context, prediction_future

            if prediction_future is None or not prediction_future.done():
                return

            inference_index, inference_timestamp, buffered_window = prediction_context
            future = prediction_future
            prediction_future = None
            prediction_context = None
            prediction = future.result()
            smoothing = smoother.update(prediction["fall_probability"])
            latest_prediction = prediction
            latest_smoothing = smoothing

            LOGGER.info(
                (
                    "Resultado #%s camera_id=%s camera=%s classe=%s queda=%.4f "
                    "media=%.4f hits=%s alerta=%s probs=%s"
                ),
                inference_index,
                self.spec.camera_id,
                self.spec.name,
                prediction["predicted_class"],
                prediction["fall_probability"],
                smoothing.moving_average,
                smoothing.consecutive_hits,
                "sim" if smoothing.alert else "nao",
                prediction.get("probabilities", {}),
            )

            if not smoothing.alert:
                return
            if inference_timestamp - last_alert_at < self.spec.alert_cooldown_seconds:
                LOGGER.info(
                    (
                        "ALERTA_QUEDA_SUPRIMIDO_COOLDOWN camera_id=%s queda=%.4f "
                        "media=%.4f hits=%s cooldown_restante=%.2fs"
                    ),
                    self.spec.camera_id,
                    prediction["fall_probability"],
                    smoothing.moving_average,
                    smoothing.consecutive_hits,
                    self.spec.alert_cooldown_seconds - (inference_timestamp - last_alert_at),
                )
                return

            last_alert_at = inference_timestamp
            # Keep receiving frames briefly after the alert. That gives the
            # encrypted history useful context on both sides of the fall.
            post_roll_until = max(inference_timestamp, timestamp) + self.spec.clip_post_seconds
            pending_alert = {
                "prediction": prediction,
                "smoothing": smoothing,
                "inference_count": inference_index,
                "clip_start": inference_timestamp - self.spec.clip_pre_seconds,
                "clip_end": post_roll_until,
                "clip_frames": [
                    item
                    for item in buffer.frames()
                    if item.timestamp >= inference_timestamp - self.spec.clip_pre_seconds
                ],
            }
            LOGGER.warning(
                (
                    "ALERTA_QUEDA_PROVAVEL camera_id=%s camera=%s source=%s queda=%.4f "
                    "media=%.4f hits=%s pre_roll=%.2fs post_roll=%.2fs timestamp=%.3f"
                ),
                self.spec.camera_id,
                self.spec.name,
                _mask_source(self.spec.source),
                prediction["fall_probability"],
                smoothing.moving_average,
                smoothing.consecutive_hits,
                self.spec.clip_pre_seconds,
                self.spec.clip_post_seconds,
                time.time(),
            )

        LOGGER.info(
            (
                "Pipeline iniciado: camera_id=%s camera=%s source=%s checkpoint=%s "
                "num_frames=%s infer_sample_fps=%.2f capture_fps=%s stride=%.2fs "
                "threshold=%.2f smoothing_window=%s min_hits=%s buffer_seconds=%.2f "
                "clip_pre=%.2fs clip_post=%.2fs freeze=%.2fs cooldown=%.2fs show_preview=%s"
            ),
            self.spec.camera_id,
            self.spec.name,
            _mask_source(self.spec.source),
            config.checkpoint,
            config.num_frames,
            config.sample_fps,
            "source" if self.spec.capture_fps is None else f"{self.spec.capture_fps:.2f}",
            config.stride_seconds,
            config.threshold,
            config.smoothing_window,
            config.min_consecutive_hits,
            config.buffer_seconds,
            self.spec.clip_pre_seconds,
            self.spec.clip_post_seconds,
            self.spec.freeze_seconds,
            self.spec.alert_cooldown_seconds,
            self.spec.show_preview,
        )
        has_frame = False
        try:
            for frame, timestamp in worker.frames(stop_event=self._stop_event, pause_event=pause_event):
                with self._latest_frame_lock:
                    self._latest_frame = frame.copy()
                consume_completed_prediction()
                if freeze_until_monotonic is not None:
                    freeze_remaining = freeze_until_monotonic - time.monotonic()
                    if freeze_remaining > 0:
                        time.sleep(min(0.25, freeze_remaining))
                        continue
                    freeze_until_monotonic = None
                    buffer.clear()
                    last_inference_at = None
                    LOGGER.info("Freeze encerrado. Inferencia retomada: camera_id=%s", self.spec.camera_id)

                if not has_frame:
                    has_frame = True
                    self._update_camera_status("online")
                buffer.append(frame, timestamp)
                if preview is not None:
                    if preview.is_alive:
                        preview.submit(
                            _render_preview_frame(
                                frame,
                                latest_prediction,
                                latest_smoothing,
                                freeze_until_monotonic,
                            )
                        )
                    else:
                        LOGGER.info("fall monitor preview closed by user: camera_id=%s", self.spec.camera_id)
                        preview.close()
                        preview = None

                if pending_alert is not None:
                    pending_alert["clip_frames"].append(buffer.frames()[-1])
                    if timestamp < pending_alert["clip_end"]:
                        continue

                    self._create_notification(
                        prediction=pending_alert["prediction"],
                        smoothing=pending_alert["smoothing"],
                        inference_count=pending_alert["inference_count"],
                        clip_frames=pending_alert["clip_frames"],
                        clip_fps=clip_capture_fps,
                    )
                    if self.spec.freeze_seconds > 0:
                        freeze_until_monotonic = time.monotonic() + self.spec.freeze_seconds
                        if preview is not None and preview.is_alive:
                            preview.submit(
                                _render_preview_frame(
                                    frame,
                                    pending_alert["prediction"],
                                    pending_alert["smoothing"],
                                    freeze_until_monotonic,
                                )
                            )
                    pending_alert = None
                    buffer.clear()
                    last_inference_at = None
                    continue

                if last_inference_at is not None and timestamp - last_inference_at < config.stride_seconds:
                    continue
                if prediction_future is not None:
                    continue

                buffered_window = buffer.sample_window_buffered(
                    num_frames=config.num_frames,
                    sample_fps=config.sample_fps,
                    end_timestamp=timestamp,
                )
                if len(buffered_window) < config.num_frames:
                    skipped_windows += 1
                    if skipped_windows == 1 or skipped_windows % 100 == 0:
                        LOGGER.info(
                            (
                                "Aguardando janela para inferencia: camera_id=%s buffer=%s "
                                "frames_janela=%s/%s sample_fps=%.2f timestamp=%.3f"
                            ),
                            self.spec.camera_id,
                            len(buffer),
                            len(buffered_window),
                            config.num_frames,
                            config.sample_fps,
                            timestamp,
                        )
                    continue

                skipped_windows = 0
                last_inference_at = timestamp
                inference_count += 1
                window = [item.frame for item in buffered_window]
                window_start = buffered_window[0].timestamp
                window_end = buffered_window[-1].timestamp
                LOGGER.info(
                    (
                        "Inferencia #%s camera_id=%s camera=%s frames=%s buffer=%s "
                        "janela=%.3fs-%.3fs checkpoint=%s"
                    ),
                    inference_count,
                    self.spec.camera_id,
                    self.spec.name,
                    len(window),
                    len(buffer),
                    window_start,
                    window_end,
                    config.checkpoint,
                )
                prediction_context = (inference_count, timestamp, buffered_window)
                prediction_future = prediction_executor.submit(
                    self.classifier_provider.predict_frames,
                    window,
                    checkpoint=config.checkpoint,
                    device=config.device,
                )
        except Exception as exc:
            self.failed_at = time.monotonic()
            LOGGER.exception("fall monitor job failed: camera_id=%s", self.spec.camera_id)
            self._update_camera_status("error", error=str(exc))
        finally:
            prediction_executor.shutdown(wait=False, cancel_futures=True)
            if preview is not None:
                preview.close()
            if not self._stop_event.is_set():
                self._update_camera_status("offline")

    def _create_notification(self, *, prediction: dict, smoothing, inference_count: int, clip_frames, clip_fps: float):
        from datetime import UTC, datetime

        from api.services.fall_events import record_fall_event

        payload = {
            "camera_id": str(self.spec.camera_id),
            "workspace_id": str(self.spec.workspace_id),
            "camera_name": self.spec.name,
            "source": _mask_source(self.spec.source),
            "inference_count": inference_count,
            "fall_probability": float(prediction["fall_probability"]),
            "predicted_class": prediction["predicted_class"],
            "probabilities": prediction.get("probabilities", {}),
            "threshold": self.spec.config.threshold,
            "moving_average": float(smoothing.moving_average),
            "consecutive_hits": int(smoothing.consecutive_hits),
        }
        with SessionLocal() as db:
            clip_result = ClipExporter(LOGGER).export_mp4(clip_frames, fps=clip_fps)
            try:
                event = record_fall_event(
                    db,
                    workspace_id=self.spec.workspace_id,
                    camera_id=self.spec.camera_id,
                    occurred_at=datetime.now(UTC),
                    clip_bytes=clip_result.path.read_bytes() if clip_result else None,
                )
            finally:
                if clip_result:
                    clip_result.path.unlink(missing_ok=True)
            notification = create_fall_detected_notification(
                db,
                workspace_id=self.spec.workspace_id,
                camera_id=self.spec.camera_id,
                payload=payload,
                body=f"Uma possível queda foi detectada pela câmera {self.spec.name}.",
                created_by="fall_monitor_job",
            )
            event.notification_id = notification.id
            db.commit()
        LOGGER.warning(
            "fall monitor notification created: camera_id=%s fall=%.4f",
            self.spec.camera_id,
            prediction["fall_probability"],
        )

    def _update_camera_status(self, status: str, error: str | None = None):
        with SessionLocal() as db:
            camera = db.get(Camera, self.spec.camera_id)
            if camera is None:
                return
            camera.status = status
            if status == "online":
                from datetime import datetime, UTC

                camera.last_seen_at = datetime.now(UTC)
            if error:
                metadata = dict(camera.metadata_json or {})
                metadata["fall_monitor_last_error"] = error
                camera.metadata_json = metadata
            db.commit()


class CameraMonitorSupervisor:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.classifier_provider = FallClassifierProvider(
            checkpoint=self.settings.fall_monitor_checkpoint,
            device=self.settings.fall_monitor_device,
        )
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._jobs: dict[uuid.UUID, CameraMonitorJob] = {}

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="fall-monitor-supervisor", daemon=True)
            self._thread.start()
        LOGGER.info("fall monitor supervisor started")

    def stop(self, timeout: float = 10.0):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._stop_all_jobs()
        LOGGER.info("fall monitor supervisor stopped")

    def reconcile_once(self):
        specs = {spec.camera_id: spec for spec in self._load_active_specs()}
        with self._lock:
            for camera_id, job in list(self._jobs.items()):
                spec = specs.get(camera_id)
                if spec is None or spec.signature != job.spec.signature:
                    job.stop()
                    self._jobs.pop(camera_id, None)
                    continue
                if not job.is_alive():
                    if not self._can_restart(job):
                        continue
                    job.stop()
                    self._jobs.pop(camera_id, None)

            for camera_id, spec in specs.items():
                if camera_id in self._jobs:
                    continue
                job = CameraMonitorJob(spec, self.classifier_provider)
                self._jobs[camera_id] = job
                job.start()

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self.reconcile_once()
            except Exception:
                LOGGER.exception("fall monitor supervisor reconcile failed")
            self._stop_event.wait(max(1.0, self.settings.fall_monitor_reload_seconds))

    def _can_restart(self, job: CameraMonitorJob) -> bool:
        if job.failed_at is None:
            return True
        elapsed = time.monotonic() - job.failed_at
        return elapsed >= max(1.0, self.settings.fall_monitor_restart_backoff_seconds)

    def snapshot_jpeg(self, camera_id: uuid.UUID) -> bytes | None:
        with self._lock:
            job = self._jobs.get(camera_id)
        return job.snapshot_jpeg() if job and job.is_alive() else None

    def _stop_all_jobs(self):
        with self._lock:
            jobs = list(self._jobs.values())
            self._jobs.clear()
        for job in jobs:
            job.stop()

    def _load_active_specs(self) -> list[CameraMonitorSpec]:
        with SessionLocal() as db:
            cameras = list(db.scalars(select(Camera).where(Camera.is_active.is_(True))).all())
            return [
                spec
                for camera in cameras
                if (spec := self._spec_from_camera(camera)) is not None
            ]

    def _spec_from_camera(self, camera: Camera) -> CameraMonitorSpec | None:
        metadata = dict(camera.metadata_json or {})
        monitor_metadata = dict(metadata.get("fall_monitor") or {})
        if monitor_metadata.get("enabled") is not True:
            return None

        config = FallDetectionConfig(
            checkpoint=Path(monitor_metadata.get("checkpoint") or self.settings.fall_monitor_checkpoint),
            num_frames=int(monitor_metadata.get("num_frames") or self.settings.fall_monitor_num_frames),
            sample_fps=float(monitor_metadata.get("sample_fps") or self.settings.fall_monitor_sample_fps),
            stride_seconds=float(monitor_metadata.get("stride_seconds") or self.settings.fall_monitor_stride_seconds),
            threshold=float(monitor_metadata.get("threshold") or self.settings.fall_monitor_threshold),
            smoothing_window=int(monitor_metadata.get("smoothing_window") or self.settings.fall_monitor_smoothing_window),
            min_consecutive_hits=int(
                monitor_metadata.get("min_consecutive_hits")
                or self.settings.fall_monitor_min_consecutive_hits
            ),
            buffer_seconds=float(monitor_metadata.get("buffer_seconds") or self.settings.fall_monitor_buffer_seconds),
            device=monitor_metadata.get("device") or self.settings.fall_monitor_device,
        )
        capture_fps = float(monitor_metadata.get("capture_fps") or self.settings.fall_monitor_capture_fps)
        if capture_fps <= 0:
            capture_fps = None
        clip_pre_seconds = max(
            0.0,
            float(
                monitor_metadata["clip_pre_seconds"]
                if "clip_pre_seconds" in monitor_metadata
                else self.settings.fall_monitor_clip_pre_seconds
            ),
        )
        clip_post_seconds = max(
            0.0,
            float(
                monitor_metadata["clip_post_seconds"]
                if "clip_post_seconds" in monitor_metadata
                else self.settings.fall_monitor_clip_post_seconds
            ),
        )
        freeze_seconds = float(
            monitor_metadata.get("freeze_seconds")
            or self.settings.fall_monitor_freeze_seconds
        )
        show_preview = bool(
            monitor_metadata.get("show_preview")
            if "show_preview" in monitor_metadata
            else self.settings.fall_monitor_show_preview
        )
        cooldown = float(
            monitor_metadata.get("alert_cooldown_seconds")
            or self.settings.fall_monitor_alert_cooldown_seconds
        )
        signature = (
            camera.stream_url,
            str(config.checkpoint),
            config.num_frames,
            config.sample_fps,
            config.stride_seconds,
            config.threshold,
            config.smoothing_window,
            config.min_consecutive_hits,
            config.buffer_seconds,
            config.device,
            capture_fps,
            clip_pre_seconds,
            clip_post_seconds,
            freeze_seconds,
            show_preview,
            cooldown,
        )
        return CameraMonitorSpec(
            camera_id=camera.id,
            workspace_id=camera.workspace_id,
            name=camera.name,
            source=camera.stream_url,
            config=config,
            capture_fps=capture_fps,
            clip_pre_seconds=clip_pre_seconds,
            clip_post_seconds=clip_post_seconds,
            freeze_seconds=freeze_seconds,
            show_preview=show_preview,
            alert_cooldown_seconds=cooldown,
            signature=signature,
        )


def _mask_source(source: str) -> str:
    if "@" not in source:
        return source
    scheme, _, rest = source.partition("://")
    credentials, _, host = rest.partition("@")
    if not credentials or not host:
        return source
    return f"{scheme}://***:***@{host}"


def _render_preview_frame(
    frame_rgb,
    prediction: dict | None,
    smoothing,
    freeze_until_monotonic: float | None,
):
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    overlay = frame_bgr.copy()
    cv2.rectangle(overlay, (12, 12), (660, 156), (20, 20, 20), -1)
    frame_bgr = cv2.addWeighted(overlay, 0.45, frame_bgr, 0.55, 0)

    freeze_remaining = 0.0
    if freeze_until_monotonic is not None:
        freeze_remaining = max(0.0, freeze_until_monotonic - time.monotonic())

    alert = bool(smoothing and smoothing.alert)
    if freeze_remaining > 0:
        title = f"FREEZE ATIVO: {int(max(1, round(freeze_remaining)))}s restantes"
        title_color = (0, 180, 255)
    elif alert:
        title = "ALERTA: queda provavel"
        title_color = (0, 0, 255)
    else:
        title = "Monitorando"
        title_color = (0, 200, 0)

    cv2.putText(frame_bgr, title, (24, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.82, title_color, 2, cv2.LINE_AA)
    if prediction is None:
        cv2.putText(
            frame_bgr,
            "Aguardando inferencia...",
            (24, 84),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    else:
        cv2.putText(
            frame_bgr,
            f"Classe: {prediction['predicted_class']}",
            (24, 84),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame_bgr,
            f"Prob. queda: {prediction['fall_probability']:.3f}  Media: {smoothing.moving_average:.3f}",
            (24, 114),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame_bgr,
            f"Hits consecutivos: {smoothing.consecutive_hits}",
            (24, 144),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    return frame_bgr
