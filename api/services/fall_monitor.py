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
from api.services.notifications import (
    create_fall_detected_notification, create_armed_person_detected_notification,
    create_confrontation_detected_notification,
)
from fall_detection import CameraWorker, FallDetectionConfig, FrameBuffer, TemporalSmoother
from fall_detection.clip_exporter import ClipExporter
from api.services.native_preview import NativePreview

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraMonitorSpec:
    camera_id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    source: str
    config: FallDetectionConfig
    capture_fps: float | None
    freeze_seconds: float
    show_preview: bool
    alert_cooldown_seconds: float
    signature: tuple[Any, ...]
    clip_pre_seconds: float = 0.0
    clip_post_seconds: float = 0.0
    fall_enabled: bool = True
    armed_config: FallDetectionConfig | None = None
    armed_alert_cooldown_seconds: float = 60.0
    confrontation_config: FallDetectionConfig | None = None
    confrontation_alert_cooldown_seconds: float = 60.0


@dataclass
class DetectionLayer:
    kind: str
    config: FallDetectionConfig
    cooldown_seconds: float
    freeze_seconds: float = 0.0
    last_inference_at: float | None = None
    last_alert_at: float = -float("inf")
    resume_at: float = -float("inf")
    inference_count: int = 0
    prediction: dict | None = None
    smoothing: Any = None
    future: Future | None = None
    pending_alert: dict | None = None

    def __post_init__(self):
        self.smoother = TemporalSmoother(
            threshold=self.config.threshold, window_size=self.config.smoothing_window,
            min_consecutive_hits=self.config.min_consecutive_hits,
        )

    @property
    def probability_key(self) -> str:
        return {"fall": "fall_probability", "armed": "armed_probability",
                "confrontation": "confrontation_probability"}[self.kind]


class FallClassifierProvider:
    def __init__(self, checkpoint: str | Path, device: str | None):
        self.default_checkpoint = Path(checkpoint)
        self.default_device = device
        self._classifiers = {}
        self._load_lock = threading.Lock()
        self._predict_lock = threading.Lock()

    def predict_frames(self, frames: list, *, checkpoint: str | Path | None = None, device: str | None = None,
                       detector: str = "fall", sample_fps: float | None = None) -> dict:
        classifier = self._get_classifier(
            Path(checkpoint) if checkpoint is not None else self.default_checkpoint,
            device if device is not None else self.default_device,
            detector,
        )
        with self._predict_lock:
            if detector in {"armed", "confrontation"} and sample_fps is not None and abs(sample_fps - classifier.sample_fps) > 1e-6:
                raise ValueError(f"Checkpoint {detector} requer sample_fps={classifier.sample_fps}; recebido {sample_fps}.")
            return classifier.predict_frames(frames)

    def _get_classifier(self, checkpoint: Path, device: str | None, detector: str = "fall"):
        key = (detector, str(checkpoint), device)
        if key in self._classifiers:
            return self._classifiers[key]
        with self._load_lock:
            if key not in self._classifiers:
                from fall_detection import FallClassifier
                from fall_detection.armed_inference import ArmedClassifier
                from fall_detection.confrontation_inference import ConfrontationClassifier

                LOGGER.info(
                    "fall monitor classifier loading: checkpoint=%s device=%s",
                    checkpoint,
                    device or "auto",
                )
                classifier_types = {"fall": FallClassifier, "armed": ArmedClassifier,
                                    "confrontation": ConfrontationClassifier}
                if detector not in classifier_types:
                    raise ValueError(f"Detector desconhecido: {detector}")
                classifier_type = classifier_types[detector]
                self._classifiers[key] = classifier_type(checkpoint, device=device)
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
        success, encoded = cv2.imencode(".jpg", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                                        [int(cv2.IMWRITE_JPEG_QUALITY), 80])
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

    def _detection_layers(self) -> list[DetectionLayer]:
        layers = []
        if self.spec.fall_enabled:
            layers.append(DetectionLayer("fall", self.spec.config,
                                         self.spec.alert_cooldown_seconds, self.spec.freeze_seconds))
        if self.spec.armed_config is not None:
            layers.append(DetectionLayer("armed", self.spec.armed_config,
                                         self.spec.armed_alert_cooldown_seconds))
        if self.spec.confrontation_config is not None:
            layers.append(DetectionLayer("confrontation", self.spec.confrontation_config,
                                         self.spec.confrontation_alert_cooldown_seconds))
        return layers

    def _monitor_loop(self):
        layers = self._detection_layers()
        estimated_fps = self.spec.capture_fps or max(30.0, *(layer.config.sample_fps for layer in layers))
        buffer = FrameBuffer(max_frames=max(
            int(max(layer.config.buffer_seconds, self.spec.clip_pre_seconds) * estimated_fps)
            + layer.config.num_frames for layer in layers
        ))
        worker = CameraWorker(self.spec.source, sample_fps=self.spec.capture_fps)
        preview = None
        if self.spec.show_preview:
            try:
                preview = NativePreview(self.spec.name)
            except Exception:
                LOGGER.exception("Preview indisponivel: camera_id=%s", self.spec.camera_id)
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="camera-inference")
        has_frame = False
        for layer in layers:
            LOGGER.info("Detector iniciado: camera_id=%s detector=%s config=%s cooldown=%.1fs",
                        self.spec.camera_id, layer.kind, layer.config, layer.cooldown_seconds)
        try:
            for frame, timestamp in worker.frames(stop_event=self._stop_event, pause_event=None):
                with self._latest_frame_lock:
                    self._latest_frame = frame.copy()
                if not has_frame:
                    has_frame = True
                    self._update_camera_status("online")
                buffer.append(frame, timestamp)
                # Cada camada tem sua propria janela, suavizacao, cooldown e pausa.
                # A captura continua mesmo quando uma camada esta em freeze.
                for layer in layers:
                    if self._stop_event.is_set():
                        break
                    try:
                        self._process_layer(layer, buffer, timestamp, executor=executor)
                    except Exception:
                        layer.smoother.reset()
                        layer.resume_at = time.monotonic() + 30.0
                        LOGGER.exception("Detector falhou; nova tentativa em 30s: camera_id=%s detector=%s",
                                         self.spec.camera_id, layer.kind)
                if preview is not None:
                    if preview.is_alive:
                        preview.submit(_render_preview_frame(frame, layers))
                    else:
                        preview.close()
                        preview = None
        except Exception as exc:
            self.failed_at = time.monotonic()
            LOGGER.exception("Monitor de camera falhou: camera_id=%s", self.spec.camera_id)
            self._update_camera_status("error", error=str(exc))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
            release = getattr(worker, "release", None)
            if release:
                release()
            if preview is not None:
                preview.close()
            if self.failed_at is None and not self._stop_event.is_set():
                self._update_camera_status("offline")

    def _process_layer(self, layer: DetectionLayer, buffer: FrameBuffer, timestamp: float, executor=None):
        config = layer.config
        if timestamp < layer.resume_at:
            return
        if layer.pending_alert is not None:
            pending = layer.pending_alert
            latest = buffer.frames()[-1]
            if not pending["frames"] or pending["frames"][-1].timestamp < pending["end"]:
                if not pending["frames"] or latest.timestamp > pending["frames"][-1].timestamp:
                    pending["frames"].append(latest)
            if timestamp >= pending["end"]:
                if self._finish_alert(layer, pending["timestamp"], clip_frames=pending["frames"]):
                    layer.pending_alert = None
            return
        if layer.future is not None:
            if not layer.future.done():
                return
            future, layer.future = layer.future, None
            prediction = future.result()
            self._accept_prediction(layer, prediction, buffer, layer.last_inference_at, timestamp)
            return
        if layer.last_inference_at is not None and timestamp - layer.last_inference_at < config.stride_seconds:
            return
        buffered_window = buffer.sample_window_buffered(
            num_frames=config.num_frames, sample_fps=config.sample_fps, end_timestamp=timestamp,
        )
        if len(buffered_window) < config.num_frames:
            return
        layer.last_inference_at = timestamp
        layer.inference_count += 1
        kwargs = dict(checkpoint=config.checkpoint, device=config.device,
                      detector=layer.kind, sample_fps=config.sample_fps)
        frames = [item.frame for item in buffered_window]
        if executor is not None:
            layer.future = executor.submit(self.classifier_provider.predict_frames, frames, **kwargs)
            return
        prediction = self.classifier_provider.predict_frames(frames, **kwargs)
        self._accept_prediction(layer, prediction, buffer, timestamp, timestamp)

    def _accept_prediction(self, layer, prediction, buffer, timestamp, current_timestamp):
        probability = float(prediction[layer.probability_key])
        smoothing = layer.smoother.update(probability)
        layer.prediction, layer.smoothing = prediction, smoothing
        LOGGER.info("Resultado camera_id=%s detector=%s inferencia=%s classe=%s prob=%.4f media=%.4f hits=%s alerta=%s",
                    self.spec.camera_id, layer.kind, layer.inference_count, prediction["predicted_class"],
                    probability, smoothing.moving_average, smoothing.consecutive_hits, smoothing.alert)
        if not smoothing.alert or timestamp - layer.last_alert_at < layer.cooldown_seconds:
            return
        if layer.kind == "fall" and (self.spec.clip_pre_seconds or self.spec.clip_post_seconds):
            layer.pending_alert = {
                "timestamp": timestamp, "end": current_timestamp + self.spec.clip_post_seconds,
                "frames": [item for item in buffer.frames()
                           if timestamp - self.spec.clip_pre_seconds <= item.timestamp <= current_timestamp],
            }
            if self.spec.clip_post_seconds > 0:
                return
            if self._finish_alert(layer, timestamp, clip_frames=layer.pending_alert["frames"]):
                layer.pending_alert = None
            return
        self._finish_alert(layer, timestamp)

    def _finish_alert(self, layer, timestamp, clip_frames=None):
        try:
            kwargs = {} if clip_frames is None else {"clip_frames": clip_frames,
                "clip_fps": self.spec.capture_fps or max(30.0, layer.config.sample_fps)}
            self._create_notification(layer=layer, timestamp=timestamp, **kwargs)
        except Exception:
            # Nao descartar o evento nem impedir a outra camada quando o banco falhar.
            LOGGER.exception("Falha ao persistir alerta: camera_id=%s detector=%s", self.spec.camera_id, layer.kind)
            return False
        layer.last_alert_at = timestamp
        if layer.freeze_seconds > 0:
            layer.resume_at = time.monotonic() + layer.freeze_seconds
            layer.smoother.reset()
        LOGGER.warning("ALERTA_CONFIRMADO camera_id=%s detector=%s prob=%.4f",
                       self.spec.camera_id, layer.kind, layer.prediction[layer.probability_key])
        return True

    def _create_notification(self, *, layer: DetectionLayer, timestamp: float, clip_frames=None, clip_fps=30.0):
        prediction, smoothing = layer.prediction, layer.smoothing
        probability = float(prediction[layer.probability_key])
        payload = {
            "camera_id": str(self.spec.camera_id),
            "workspace_id": str(self.spec.workspace_id),
            "camera_name": self.spec.name,
            "source": _mask_source(self.spec.source),
            "detector": layer.kind,
            "checkpoint": str(layer.config.checkpoint),
            "inference_count": layer.inference_count,
            layer.probability_key: probability,
            "confidence": probability * 100,
            "predicted_class": prediction["predicted_class"],
            "probabilities": prediction.get("probabilities", {}),
            "threshold": layer.config.threshold,
            "moving_average": float(smoothing.moving_average),
            "consecutive_hits": int(smoothing.consecutive_hits),
            "monitor_timestamp": float(timestamp),
        }
        create_notification, event_description = {
            "fall": (create_fall_detected_notification, "Uma possivel queda foi detectada"),
            "armed": (create_armed_person_detected_notification, "Uma possivel pessoa armada foi detectada"),
            "confrontation": (create_confrontation_detected_notification, "Um possivel confronto foi detectado"),
        }[layer.kind]
        with SessionLocal() as db:
            event = None
            if layer.kind == "fall":
                from datetime import UTC, datetime
                from api.services.fall_events import record_fall_event

                clip = ClipExporter(LOGGER).export_mp4(clip_frames, fps=clip_fps) if clip_frames else None
                try:
                    event = record_fall_event(db, workspace_id=self.spec.workspace_id,
                        camera_id=self.spec.camera_id, occurred_at=datetime.now(UTC),
                        clip_bytes=clip.path.read_bytes() if clip else None)
                finally:
                    if clip:
                        clip.path.unlink(missing_ok=True)
            notification = create_notification(
                db, workspace_id=self.spec.workspace_id, camera_id=self.spec.camera_id,
                payload=payload,
                body=f"{event_description} pela camera {self.spec.name}.",
                created_by=f"{layer.kind}_monitor_job",
            )
            if event is not None:
                event.notification_id = notification.id
                db.commit()

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

    def _stop_all_jobs(self):
        with self._lock:
            jobs = list(self._jobs.values())
            self._jobs.clear()
        for job in jobs:
            job.stop()

    def snapshot_jpeg(self, camera_id: uuid.UUID) -> bytes | None:
        with self._lock:
            job = self._jobs.get(camera_id)
        return job.snapshot_jpeg() if job and job.is_alive() else None

    def _load_active_specs(self) -> list[CameraMonitorSpec]:
        with SessionLocal() as db:
            cameras = list(db.scalars(select(Camera).where(Camera.is_active.is_(True))).all())
            specs = []
            for camera in cameras:
                try:
                    spec = self._spec_from_camera(camera)
                except (TypeError, ValueError):
                    LOGGER.exception("Configuracao invalida: camera_id=%s", camera.id)
                    continue
                if spec is not None:
                    specs.append(spec)
            return specs

    def _spec_from_camera(self, camera: Camera) -> CameraMonitorSpec | None:
        metadata = dict(camera.metadata_json or {})
        monitor_metadata = dict(metadata.get("fall_monitor") or {})
        armed_metadata = dict(metadata.get("armed_monitor") or {})
        confrontation_metadata = dict(metadata.get("confrontation_monitor") or {})
        fall_enabled = monitor_metadata.get("enabled") is True
        armed_enabled = armed_metadata.get("enabled", self.settings.armed_monitor_enabled and fall_enabled) is True
        confrontation_enabled = confrontation_metadata.get(
            "enabled", self.settings.confrontation_monitor_enabled and (fall_enabled or armed_enabled)
        ) is True
        if not (fall_enabled or armed_enabled or confrontation_enabled):
            return None

        def detection_config(values: dict, prefix: str) -> FallDetectionConfig:
            names = ("checkpoint", "num_frames", "sample_fps", "stride_seconds", "threshold",
                     "smoothing_window", "min_consecutive_hits", "buffer_seconds", "device")
            config_values = {name: values.get(name, getattr(self.settings, f"{prefix}_monitor_{name}")) for name in names}
            config_values["checkpoint"] = Path(config_values["checkpoint"])
            for name in ("num_frames", "smoothing_window", "min_consecutive_hits"):
                config_values[name] = int(config_values[name])
            for name in ("sample_fps", "stride_seconds", "threshold", "buffer_seconds"):
                config_values[name] = float(config_values[name])
            return FallDetectionConfig(**config_values)

        armed_config = detection_config(armed_metadata, "armed") if armed_enabled else None
        confrontation_config = detection_config(confrontation_metadata, "confrontation") if confrontation_enabled else None
        config = detection_config(monitor_metadata, "fall") if fall_enabled else (armed_config or confrontation_config)
        capture_metadata = monitor_metadata if fall_enabled else (armed_metadata if armed_enabled else confrontation_metadata)
        capture_fps = float(capture_metadata.get("capture_fps", self.settings.fall_monitor_capture_fps))
        capture_fps = capture_fps if capture_fps > 0 else None
        clip_pre = max(0.0, float(monitor_metadata.get("clip_pre_seconds", self.settings.fall_monitor_clip_pre_seconds)))
        clip_post = max(0.0, float(monitor_metadata.get("clip_post_seconds", self.settings.fall_monitor_clip_post_seconds)))
        freeze_seconds = float(monitor_metadata.get("freeze_seconds", self.settings.fall_monitor_freeze_seconds))
        show_preview = bool(capture_metadata.get("show_preview", self.settings.fall_monitor_show_preview))
        cooldown = float(monitor_metadata.get("alert_cooldown_seconds", self.settings.fall_monitor_alert_cooldown_seconds))
        armed_cooldown = float(armed_metadata.get("alert_cooldown_seconds", self.settings.armed_monitor_alert_cooldown_seconds))
        confrontation_cooldown = float(confrontation_metadata.get("alert_cooldown_seconds", self.settings.confrontation_monitor_alert_cooldown_seconds))
        if min(freeze_seconds, cooldown, armed_cooldown, confrontation_cooldown) < 0:
            raise ValueError("Freeze e cooldown nao podem ser negativos.")
        signature = (camera.stream_url, camera.name, camera.workspace_id, config, armed_config, confrontation_config,
                     fall_enabled, capture_fps, clip_pre, clip_post, freeze_seconds, show_preview, cooldown, armed_cooldown, confrontation_cooldown)
        return CameraMonitorSpec(
            camera_id=camera.id, workspace_id=camera.workspace_id, name=camera.name,
            source=camera.stream_url, config=config, capture_fps=capture_fps,
            clip_pre_seconds=clip_pre, clip_post_seconds=clip_post,
            freeze_seconds=freeze_seconds, show_preview=show_preview,
            alert_cooldown_seconds=cooldown, signature=signature, fall_enabled=fall_enabled,
            armed_config=armed_config, armed_alert_cooldown_seconds=armed_cooldown,
            confrontation_config=confrontation_config, confrontation_alert_cooldown_seconds=confrontation_cooldown,
        )



def _mask_source(source: str) -> str:
    if "@" not in source:
        return source
    scheme, _, rest = source.partition("://")
    credentials, _, host = rest.partition("@")
    if not credentials or not host:
        return source
    return f"{scheme}://***:***@{host}"


def _render_preview_frame(frame_rgb, layers: list[DetectionLayer]):
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    overlay = frame_bgr.copy()
    cv2.rectangle(overlay, (12, 12), (780, 60 + 64 * len(layers)), (20, 20, 20), -1)
    frame_bgr = cv2.addWeighted(overlay, 0.45, frame_bgr, 0.55, 0)
    cv2.putText(frame_bgr, "VARD - Monitoramento", (24, 42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    for index, layer in enumerate(layers):
        label = {"armed": "Pessoa armada", "fall": "Queda", "confrontation": "Confronto"}[layer.kind]
        text = f"{label}: aguardando janela"
        color = (0, 200, 0)
        if layer.prediction is not None:
            text = (f"{label}: {layer.prediction[layer.probability_key]:.3f} "
                    f"media={layer.smoothing.moving_average:.3f} hits={layer.smoothing.consecutive_hits}")
            if layer.smoothing.alert:
                text += " ALERTA"
                color = (0, 0, 255)
        remaining = layer.resume_at - time.monotonic()
        if remaining > 0:
            text += f" pausa={remaining:.0f}s"
        cv2.putText(frame_bgr, text, (24, 82 + index * 64),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
    return frame_bgr
