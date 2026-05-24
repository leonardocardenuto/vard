from __future__ import annotations

import argparse
import logging
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

try:
    import winsound
except ImportError:  # pragma: no cover - fallback fora do Windows
    winsound = None

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fall_detection import CameraWorker, FallClassifier, FallDetectionConfig, FrameBuffer, TemporalSmoother
from fall_detection.clip_exporter import ClipExporter


@dataclass
class LatestInferenceState:
    prediction: dict | None = None
    moving_average: float | None = None
    consecutive_hits: int | None = None
    alert: bool = False
    inference_count: int = 0
    window_end_timestamp: float | None = None
    window_frames: list | None = None


class RuntimeState:
    def __init__(self):
        self._lock = threading.Lock()
        self._latest_frame = None
        self._latest_inference = LatestInferenceState()
        self._error: Exception | None = None

    def update_frame(self, frame_rgb, timestamp: float):
        with self._lock:
            self._latest_frame = frame_rgb
            self._latest_frame_timestamp = timestamp

    def update_inference(
        self,
        prediction: dict,
        moving_average: float,
        consecutive_hits: int,
        alert: bool,
        inference_count: int,
        window_end_timestamp: float,
        window_frames: list,
    ):
        with self._lock:
            self._latest_inference = LatestInferenceState(
                prediction=prediction,
                moving_average=moving_average,
                consecutive_hits=consecutive_hits,
                alert=alert,
                inference_count=inference_count,
                window_end_timestamp=window_end_timestamp,
                window_frames=window_frames,
            )

    def set_error(self, error: Exception):
        with self._lock:
            if self._error is None:
                self._error = error

    def get_error(self) -> Exception | None:
        with self._lock:
            return self._error

    def snapshot(self):
        with self._lock:
            return self._latest_frame, self._latest_inference, self._error


def parse_args():
    parser = argparse.ArgumentParser(
        description="Roda deteccao continua de queda a partir de video local, webcam ou RTSP/IP camera."
    )
    parser.add_argument("--source", required=True, help="Arquivo de video, URL RTSP/HTTP ou indice de webcam.")
    parser.add_argument(
        "--mode",
        choices=("clip", "stream"),
        default="clip",
        help="clip processa um unico trecho do video; stream roda inferencia continua em janelas.",
    )
    parser.add_argument(
        "--checkpoint",
        default="best_vjepa2_fall_classifier.pt",
        help="Checkpoint treinado do classificador V-JEPA2.",
    )
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--start-frame", type=int, default=None)
    parser.add_argument("--end-frame", type=int, default=None)
    parser.add_argument(
        "--sliding-windows",
        action="store_true",
        help="No modo clip, analisa o video em multiplas janelas deslizantes em vez de uma unica amostra.",
    )
    parser.add_argument("--sample-fps", type=float, default=6.0)
    parser.add_argument(
        "--capture-fps",
        type=float,
        default=0.0,
        help="Limita a captura/preview. Use 0 para consumir no FPS nativo do stream.",
    )
    parser.add_argument("--stride-seconds", type=float, default=1.0)
    parser.add_argument("--threshold", type=float, default=0.75)
    parser.add_argument("--smoothing-window", type=int, default=5)
    parser.add_argument("--min-consecutive-hits", type=int, default=2)
    parser.add_argument("--buffer-seconds", type=float, default=8.0)
    parser.add_argument(
        "--show-preview",
        action="store_true",
        help="Abre uma janela com o frame atual, predicao e status do alerta.",
    )
    parser.add_argument(
        "--window-name",
        default="VARD Fall Detection",
        help="Titulo da janela de preview.",
    )
    parser.add_argument(
        "--preview-mode",
        choices=("live", "window"),
        default="live",
        help="live mostra o frame mais recente; window mostra a ultima janela enviada ao modelo.",
    )
    parser.add_argument(
        "--webcam-backend",
        choices=("auto", "dshow", "msmf"),
        default="auto",
        help="Backend OpenCV usado ao abrir webcam no Windows.",
    )
    parser.add_argument("--device", default=None, help="cuda, cpu ou vazio para autodetectar.")
    parser.add_argument(
        "--save-fall-windows",
        action="store_true",
        help="Salva localmente cada janela inferida que disparar deteccao de queda.",
    )
    parser.add_argument(
        "--fall-save-dir",
        default="var/fall_windows",
        help="Diretorio onde as janelas detectadas como queda serao salvas em modo de teste.",
    )
    parser.add_argument(
        "--max-inferences",
        type=int,
        default=0,
        help="Limita inferencias para testes. Use 0 para rodar ate o fim do video/stream.",
    )
    return parser.parse_args()


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _play_window_change_sound():
    if winsound is None:
        return
    try:
        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_NOSTOP)
    except RuntimeError:
        try:
            winsound.Beep(660, 70)
        except RuntimeError:
            pass


def _draw_preview(
    frame_rgb,
    prediction: dict | None,
    moving_average: float | None,
    consecutive_hits: int | None,
    alert: bool,
):
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    overlay = frame_bgr.copy()
    cv2.rectangle(overlay, (12, 12), (620, 148), (20, 20, 20), -1)
    frame_bgr = cv2.addWeighted(overlay, 0.45, frame_bgr, 0.55, 0)

    title_color = (0, 0, 255) if alert else (0, 200, 0)
    title_text = "ALERTA: queda provavel" if alert else "Monitorando"
    cv2.putText(frame_bgr, title_text, (24, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.85, title_color, 2, cv2.LINE_AA)

    if prediction is None:
        cv2.putText(
            frame_bgr,
            "Aguardando janela suficiente para inferencia...",
            (24, 78),
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
            (24, 78),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame_bgr,
            f"Prob. queda: {prediction['fall_probability']:.3f}  Media: {(moving_average or 0.0):.3f}",
            (24, 106),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame_bgr,
            f"Hits consecutivos: {consecutive_hits or 0}",
            (24, 134),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    return frame_bgr


def _build_window_preview(window_frames: list[np.ndarray], fallback_frame_rgb) -> np.ndarray:
    if not window_frames:
        return cv2.cvtColor(fallback_frame_rgb, cv2.COLOR_RGB2BGR)

    thumb_width = 200
    thumb_height = 112
    max_columns = 5
    rows = []

    for start in range(0, len(window_frames), max_columns):
        row_frames = []
        for frame_rgb in window_frames[start : start + max_columns]:
            frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
            thumb = cv2.resize(frame_bgr, (thumb_width, thumb_height), interpolation=cv2.INTER_AREA)
            row_frames.append(thumb)

        while len(row_frames) < max_columns:
            row_frames.append(np.zeros((thumb_height, thumb_width, 3), dtype=np.uint8))
        rows.append(cv2.hconcat(row_frames))

    return cv2.vconcat(rows)


def _show_preview(window_name: str, frame_rgb, prediction, moving_average, consecutive_hits, alert: bool) -> bool:
    preview_frame = _draw_preview(frame_rgb, prediction, moving_average, consecutive_hits, alert)
    cv2.imshow(window_name, preview_frame)
    key = cv2.waitKey(1) & 0xFF
    return key in (27, ord("q"))


def _show_window_preview(window_name: str, frame_rgb, inference_state: LatestInferenceState) -> bool:
    base_frame_bgr = _build_window_preview(inference_state.window_frames or [], frame_rgb)
    preview_frame = _draw_preview(
        cv2.cvtColor(base_frame_bgr, cv2.COLOR_BGR2RGB),
        inference_state.prediction,
        inference_state.moving_average,
        inference_state.consecutive_hits,
        inference_state.alert,
    )
    cv2.putText(
        preview_frame,
        "Preview: ultima janela inferida",
        (24, preview_frame.shape[0] - 18),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.imshow(window_name, preview_frame)
    key = cv2.waitKey(1) & 0xFF
    return key in (27, ord("q"))


def _capture_loop(
    worker: CameraWorker,
    buffer: FrameBuffer,
    runtime: RuntimeState,
    stop_event: threading.Event,
    logger: logging.Logger,
):
    try:
        for frame, timestamp in worker.frames(stop_event=stop_event):
            buffer.append(frame, timestamp)
            runtime.update_frame(frame, timestamp)
    except Exception as exc:
        logger.exception("Falha no loop de captura.")
        runtime.set_error(exc)
    finally:
        stop_event.set()


def _inference_loop(
    classifier: FallClassifier,
    buffer: FrameBuffer,
    runtime: RuntimeState,
    stop_event: threading.Event,
    config: FallDetectionConfig,
    args,
    logger: logging.Logger,
):
    smoother = TemporalSmoother(
        threshold=config.threshold,
        window_size=config.smoothing_window,
        min_consecutive_hits=config.min_consecutive_hits,
    )
    clip_exporter = ClipExporter(logger=logger)
    last_inference_at: float | None = None
    inference_count = 0

    while not stop_event.is_set():
        latest_timestamp = buffer.latest_timestamp()
        if latest_timestamp is None:
            time.sleep(0.01)
            continue

        if last_inference_at is not None and latest_timestamp - last_inference_at < config.stride_seconds:
            time.sleep(0.01)
            continue

        buffered_window = buffer.sample_window_buffered(
            num_frames=config.num_frames,
            sample_fps=config.sample_fps,
            end_timestamp=latest_timestamp,
        )
        if len(buffered_window) < config.num_frames:
            time.sleep(0.01)
            continue

        last_inference_at = latest_timestamp
        inference_count += 1
        _play_window_change_sound()
        logger.info("Inferencia #%s com %s frames no buffer.", inference_count, len(buffer))
        window = [item.frame for item in buffered_window]

        try:
            prediction = classifier.predict_frames(window)
        except Exception as exc:
            logger.exception("Falha durante a inferencia.")
            runtime.set_error(exc)
            stop_event.set()
            break

        smoothing = smoother.update(prediction["fall_probability"])
        runtime.update_inference(
            prediction=prediction,
            moving_average=smoothing.moving_average,
            consecutive_hits=smoothing.consecutive_hits,
            alert=smoothing.alert,
            inference_count=inference_count,
            window_end_timestamp=latest_timestamp,
            window_frames=list(window),
        )

        logger.info(
            "Resultado #%s: classe=%s queda=%.4f media=%.4f hits=%s probs=%s",
            inference_count,
            prediction["predicted_class"],
            prediction["fall_probability"],
            smoothing.moving_average,
            smoothing.consecutive_hits,
            prediction["probabilities"],
        )

        if smoothing.alert:
            logger.warning(
                "ALERTA_QUEDA_PROVAVEL source=%s queda=%.4f media=%.4f hits=%s timestamp=%.3f",
                args.source,
                prediction["fall_probability"],
                smoothing.moving_average,
                smoothing.consecutive_hits,
                time.time(),
            )
            if args.save_fall_windows:
                export_result = clip_exporter.export_mp4(
                    buffered_window,
                    fps=config.sample_fps,
                    output_dir=args.fall_save_dir,
                    prefix=(
                        f"fall_window_{inference_count:04d}_"
                        f"{prediction['predicted_class']}_{prediction['fall_probability']:.3f}".replace(".", "_")
                    ),
                )
                if export_result is not None:
                    logger.info("Janela de queda salva em %s", export_result.path)
                else:
                    logger.warning("Nao foi possivel salvar a janela de queda da inferencia #%s.", inference_count)

        if args.max_inferences and inference_count >= args.max_inferences:
            logger.info("Encerrando por --max-inferences=%s.", args.max_inferences)
            stop_event.set()
            break

    return inference_count


def main():
    configure_logging()
    args = parse_args()
    logger = logging.getLogger("fall_detection.cli")

    config = FallDetectionConfig(
        checkpoint=Path(args.checkpoint),
        num_frames=args.num_frames,
        sample_fps=args.sample_fps,
        stride_seconds=args.stride_seconds,
        threshold=args.threshold,
        smoothing_window=args.smoothing_window,
        min_consecutive_hits=args.min_consecutive_hits,
        buffer_seconds=args.buffer_seconds,
        device=args.device,
    )

    classifier = FallClassifier(config.checkpoint, device=config.device)

    if args.mode == "clip":
        if args.sliding_windows:
            smoother = TemporalSmoother(
                threshold=config.threshold,
                window_size=config.smoothing_window,
                min_consecutive_hits=config.min_consecutive_hits,
            )
            predictions = classifier.predict_video_windows(
                args.source,
                num_frames=config.num_frames,
                sample_fps=config.sample_fps,
                stride_seconds=config.stride_seconds,
                start_frame=args.start_frame,
                end_frame=args.end_frame,
            )
            logger.info(
                "Fluxo clip deslizante concluido para source=%s janelas=%s",
                args.source,
                len(predictions),
            )
            print("\n=== Sliding Window Predictions ===", flush=True)
            for prediction in predictions:
                smoothing = smoother.update(prediction["fall_probability"])
                print(
                    (
                        f"janela={prediction['window_index']:03d} "
                        f"tempo={prediction['start_time_seconds']:.2f}s-{prediction['end_time_seconds']:.2f}s "
                        f"frames={prediction['start_frame']}-{prediction['end_frame']} "
                        f"classe={prediction['predicted_class']} "
                        f"queda={prediction['fall_probability']:.4f} "
                        f"media={smoothing.moving_average:.4f} "
                        f"hits={smoothing.consecutive_hits} "
                        f"alerta={'sim' if smoothing.alert else 'nao'}"
                    ),
                    flush=True,
                )
            return

        prediction = classifier.predict_video_file(
            args.source,
            num_frames=config.num_frames,
            start_frame=args.start_frame,
            end_frame=args.end_frame,
        )
        logger.info("Fluxo clip concluido para source=%s", args.source)
        print("\n=== Prediction ===", flush=True)
        print(f"classe_predita: {prediction['predicted_class']}", flush=True)
        for class_name, probability in prediction["probabilities"].items():
            print(f"{class_name}: {probability:.4f}", flush=True)
        print(f"fall_probability: {prediction['fall_probability']:.4f}", flush=True)
        return

    capture_fps = args.capture_fps if args.capture_fps > 0 else None
    estimated_capture_fps = capture_fps or max(args.sample_fps, 30.0)
    worker = CameraWorker(
        args.source,
        sample_fps=capture_fps,
        webcam_backend=args.webcam_backend,
    )
    buffer = FrameBuffer(
        max_frames=max(
            config.num_frames,
            int(config.buffer_seconds * estimated_capture_fps) + config.num_frames,
        )
    )
    runtime = RuntimeState()
    stop_event = threading.Event()

    logger.info(
        (
            "Pipeline iniciado: source=%s mode=%s num_frames=%s infer_sample_fps=%.2f "
            "capture_fps=%s stride=%.2fs threshold=%.2f"
        ),
        args.source,
        args.mode,
        config.num_frames,
        config.sample_fps,
        "source" if capture_fps is None else f"{capture_fps:.2f}",
        config.stride_seconds,
        config.threshold,
    )

    capture_thread = threading.Thread(
        target=_capture_loop,
        args=(worker, buffer, runtime, stop_event, logger),
        name="fall-capture",
        daemon=True,
    )
    capture_thread.start()

    inference_thread = threading.Thread(
        target=_inference_loop,
        args=(classifier, buffer, runtime, stop_event, config, args, logger),
        name="fall-inference",
        daemon=True,
    )
    inference_thread.start()

    if args.show_preview:
        logger.info("Preview habilitado. Pressione 'q' ou ESC para encerrar.")

    try:
        while not stop_event.is_set():
            latest_frame, latest_inference, error = runtime.snapshot()
            if error is not None:
                raise error

            if args.show_preview and latest_frame is not None:
                if args.preview_mode == "window":
                    should_exit = _show_window_preview(args.window_name, latest_frame, latest_inference)
                else:
                    should_exit = _show_preview(
                        args.window_name,
                        latest_frame,
                        latest_inference.prediction,
                        latest_inference.moving_average,
                        latest_inference.consecutive_hits,
                        latest_inference.alert,
                    )
                if should_exit:
                    logger.info("Encerrando por comando do usuario na janela de preview.")
                    stop_event.set()
                    break
            else:
                time.sleep(0.01)
    except KeyboardInterrupt:
        logger.info("Encerrando por interrupcao do usuario.")
        stop_event.set()
    finally:
        stop_event.set()
        capture_thread.join(timeout=5.0)
        inference_thread.join(timeout=5.0)

    logger.info(
        "Pipeline encerrado. Frames capturados=%s inferencias=%s",
        worker.captured_frames,
        runtime.snapshot()[1].inference_count,
    )
    if args.show_preview:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
