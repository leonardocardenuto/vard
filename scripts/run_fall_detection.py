from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fall_detection import CameraWorker, FallClassifier, FallDetectionConfig, FrameBuffer, TemporalSmoother


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
    parser.add_argument("--sample-fps", type=float, default=6.0)
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
        "--webcam-backend",
        choices=("auto", "dshow", "msmf"),
        default="auto",
        help="Backend OpenCV usado ao abrir webcam no Windows.",
    )
    parser.add_argument("--device", default=None, help="cuda, cpu ou vazio para autodetectar.")
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


def _show_preview(window_name: str, frame_rgb, prediction, moving_average, consecutive_hits, alert: bool) -> bool:
    preview_frame = _draw_preview(frame_rgb, prediction, moving_average, consecutive_hits, alert)
    cv2.imshow(window_name, preview_frame)
    key = cv2.waitKey(1) & 0xFF
    return key in (27, ord("q"))


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

    worker = CameraWorker(
        args.source,
        sample_fps=config.sample_fps,
        webcam_backend=args.webcam_backend,
    )
    buffer = FrameBuffer(max_frames=config.buffer_max_frames)
    smoother = TemporalSmoother(
        threshold=config.threshold,
        window_size=config.smoothing_window,
        min_consecutive_hits=config.min_consecutive_hits,
    )

    logger.info(
        "Pipeline iniciado: source=%s mode=%s num_frames=%s sample_fps=%.2f stride=%.2fs threshold=%.2f",
        args.source,
        args.mode,
        config.num_frames,
        config.sample_fps,
        config.stride_seconds,
        config.threshold,
    )

    last_inference_at = 0.0
    inference_count = 0
    latest_prediction = None
    latest_moving_average = None
    latest_consecutive_hits = None
    latest_alert = False

    if args.show_preview:
        logger.info("Preview habilitado. Pressione 'q' ou ESC para encerrar.")

    for frame, timestamp in worker.frames():
        buffer.append(frame, timestamp)
        if args.show_preview:
            should_exit = _show_preview(
                args.window_name,
                frame,
                latest_prediction,
                latest_moving_average,
                latest_consecutive_hits,
                latest_alert,
            )
            if should_exit:
                logger.info("Encerrando por comando do usuario na janela de preview.")
                break

        if timestamp - last_inference_at < config.stride_seconds:
            continue

        window = buffer.sample_window(
            num_frames=config.num_frames,
            sample_fps=config.sample_fps,
            end_timestamp=timestamp,
        )
        if len(window) < config.num_frames:
            continue

        last_inference_at = timestamp
        inference_count += 1
        logger.info("Inferencia #%s com %s frames no buffer.", inference_count, len(buffer))

        prediction = classifier.predict_frames(window)
        smoothing = smoother.update(prediction["fall_probability"])
        latest_prediction = prediction
        latest_moving_average = smoothing.moving_average
        latest_consecutive_hits = smoothing.consecutive_hits
        latest_alert = smoothing.alert

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

        if args.max_inferences and inference_count >= args.max_inferences:
            logger.info("Encerrando por --max-inferences=%s.", args.max_inferences)
            break

    logger.info(
        "Pipeline encerrado. Frames capturados=%s inferencias=%s",
        worker.captured_frames,
        inference_count,
    )
    if args.show_preview:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
