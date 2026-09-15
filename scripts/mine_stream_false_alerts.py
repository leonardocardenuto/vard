from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections import deque
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fall_detection.inference import FallClassifier
from fall_detection.temporal_smoother import TemporalSmoother


VIDEO_EXTENSIONS = {".avi", ".mp4", ".mov", ".mkv", ".m4v"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Roda o modelo como stream em videos sem queda e minera falsos alertas/hard negatives."
    )
    parser.add_argument("--input", required=True, help="Arquivo de video ou diretorio com videos.")
    parser.add_argument("--checkpoint", default="var/best_vjepa2_fall_classifier_combined.pt")
    parser.add_argument("--output", default="artifacts/manifests/stream_hard_negatives.jsonl")
    parser.add_argument("--report", default="artifacts/reports/stream_false_alerts_report.json")
    parser.add_argument("--dataset", default="stream_negatives")
    parser.add_argument("--sample-fps", type=float, default=None)
    parser.add_argument("--window-seconds", type=float, default=None)
    parser.add_argument("--min-window-seconds", type=float, default=None)
    parser.add_argument("--no-variable-windows", action="store_true")
    parser.add_argument("--no-adaptive-short-videos", action="store_true")
    parser.add_argument("--stride-seconds", type=float, default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--smoothing-window", type=int, default=None)
    parser.add_argument("--min-consecutive-hits", type=int, default=None)
    parser.add_argument(
        "--alert-mode",
        choices=("consecutive", "average", "consecutive_or_average"),
        default=None,
    )
    parser.add_argument("--min-hard-negative-probability", type=float, default=0.5)
    parser.add_argument("--max-videos", type=int, default=0)
    parser.add_argument("--max-duration-seconds", type=float, default=0.0)
    parser.add_argument("--alert-cooldown-seconds", type=float, default=None)
    parser.add_argument("--device", default=None)
    return parser.parse_args()


def iter_videos(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(
        item
        for item in path.rglob("*")
        if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS
    )


def load_metadata(checkpoint: Path) -> dict:
    if checkpoint.suffix != ".pkl":
        return {}
    with checkpoint.open("rb") as checkpoint_file:
        return pickle.load(checkpoint_file).get("metadata", {})


def source_fps(cap) -> float:
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    return fps if fps > 0 else 30.0


def effective_window_samples(
    buffered_samples: int,
    full_window_samples: int,
    min_window_samples: int,
    variable_windows: bool,
) -> int:
    if buffered_samples >= full_window_samples:
        return full_window_samples
    if variable_windows and buffered_samples >= min_window_samples:
        return buffered_samples
    return 0


def adapt_config_for_video(config: dict, duration_seconds: float) -> dict:
    adapted = dict(config)
    if not adapted.get("adaptive_short_video_windows", True):
        return adapted
    if duration_seconds <= 0:
        return adapted

    full_window_seconds = float(adapted["window_seconds"])
    if duration_seconds >= full_window_seconds:
        return adapted

    short_window_seconds = max(
        0.75,
        min(full_window_seconds, duration_seconds * 0.90),
    )
    adapted["min_window_seconds"] = min(float(adapted["min_window_seconds"]), short_window_seconds)
    adapted["window_seconds"] = short_window_seconds
    adapted["stride_seconds"] = min(float(adapted["stride_seconds"]), max(0.25, short_window_seconds / 3.0))
    adapted["smoothing_window"] = 1
    adapted["min_consecutive_hits"] = 1
    adapted["alert_mode"] = "consecutive"
    adapted["adaptive_short_video_applied"] = True
    return adapted


def run_video(
    video_path: Path,
    classifier: FallClassifier,
    config: dict,
    dataset: str,
    min_hard_negative_probability: float,
    max_duration_seconds: float,
) -> tuple[list[dict], dict]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return [], {"video_path": str(video_path), "error": "open_failed"}

    fps = source_fps(cap)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_seconds = total_frames / fps if total_frames > 0 else 0.0
    if max_duration_seconds > 0:
        duration_seconds = min(duration_seconds, max_duration_seconds)
    config = adapt_config_for_video(config, duration_seconds)

    sample_fps = float(config["sample_fps"])
    window_seconds = float(config["window_seconds"])
    min_window_seconds = float(config["min_window_seconds"])
    variable_windows = bool(config["variable_windows"])
    stride_seconds = float(config["stride_seconds"])
    buffer_max_frames = max(1, int(round(window_seconds * sample_fps)) + int(round(sample_fps)))
    sample_interval = max(1, int(round(fps / sample_fps)))
    stride_samples = max(1, int(round(stride_seconds * sample_fps)))
    full_window_samples = max(1, int(round(window_seconds * sample_fps)))
    min_window_samples = max(1, int(round(min_window_seconds * sample_fps)))

    smoother = TemporalSmoother(
        threshold=float(config["threshold"]),
        window_size=int(config["smoothing_window"]),
        min_consecutive_hits=int(config["min_consecutive_hits"]),
        alert_mode=str(config["alert_mode"]),
    )
    frame_buffer = deque(maxlen=buffer_max_frames)
    index_buffer = deque(maxlen=buffer_max_frames)
    mined = []
    probabilities = []
    alert_count = 0
    alert_active = False
    last_alert_event_time = -float("inf")
    sampled_count = 0
    processed_frames = 0

    while True:
        ok, frame_bgr = cap.read()
        if not ok:
            break
        frame_index = processed_frames
        processed_frames += 1
        timestamp = frame_index / fps
        if max_duration_seconds > 0 and timestamp > max_duration_seconds:
            break
        if frame_index % sample_interval != 0:
            continue

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_buffer.append(frame_rgb)
        index_buffer.append(frame_index)
        sampled_count += 1
        window_samples = effective_window_samples(
            len(frame_buffer),
            full_window_samples,
            min_window_samples,
            variable_windows,
        )
        if window_samples <= 0 or sampled_count % stride_samples != 0:
            continue

        frames = list(frame_buffer)[-window_samples:]
        indices = list(index_buffer)[-window_samples:]
        prediction = classifier.predict_frames(frames, sample_fps=sample_fps)
        probability = float(prediction["fall_probability"])
        probabilities.append(probability)
        smoothing = smoother.update(probability)

        window_start_frame = int(indices[0])
        window_end_frame = int(indices[-1])
        window_start_time = window_start_frame / fps
        window_end_time = window_end_frame / fps
        if probability >= min_hard_negative_probability or smoothing.alert:
            mined.append(
                {
                    "video_path": str(video_path),
                    "dataset": dataset,
                    "group_id": str(video_path),
                    "start_frame": window_start_frame,
                    "end_frame": window_end_frame,
                    "start_time": window_start_time,
                    "end_time": window_end_time,
                    "label": "sem_queda",
                    "fps": fps,
                    "fall_probability": probability,
                    "effective_window_seconds": window_end_time - window_start_time,
                    "effective_window_samples": int(window_samples),
                    "variable_window": bool(window_samples < full_window_samples),
                    "moving_average": float(smoothing.moving_average),
                    "consecutive_hits": int(smoothing.consecutive_hits),
                    "alert": bool(smoothing.alert),
                    "review_status": "pending",
                    "source": "stream_false_alert_mining",
                }
            )
        cooldown_seconds = float(config.get("alert_cooldown_seconds") or 0.0)
        cooldown_ready = window_end_time - last_alert_event_time >= cooldown_seconds
        if smoothing.alert and not alert_active and cooldown_ready:
            alert_count += 1
            last_alert_event_time = window_end_time
            alert_active = True
        if not smoothing.alert:
            alert_active = False

    cap.release()
    negative_hours = duration_seconds / 3600.0 if duration_seconds > 0 else processed_frames / fps / 3600.0
    summary = {
        "video_path": str(video_path),
        "fps": fps,
        "duration_seconds": duration_seconds,
        "processed_frames": processed_frames,
        "sampled_frames": sampled_count,
        "inferences": len(probabilities),
        "mined_windows": len(mined),
        "alert_events": alert_count,
        "false_alerts_per_hour": 0.0 if negative_hours <= 0 else alert_count / negative_hours,
        "max_probability": float(max(probabilities)) if probabilities else 0.0,
        "mean_probability": float(np.mean(probabilities)) if probabilities else 0.0,
        "variable_windows": variable_windows,
        "window_seconds": window_seconds,
        "min_window_seconds": min_window_seconds,
        "adaptive_short_video_applied": bool(config.get("adaptive_short_video_applied", False)),
    }
    return mined, summary


def main():
    args = parse_args()
    checkpoint = Path(args.checkpoint)
    metadata = load_metadata(checkpoint)
    config = {
        "sample_fps": args.sample_fps or metadata.get("production_sample_fps") or 6.0,
        "window_seconds": args.window_seconds or metadata.get("production_window_seconds") or 5.0,
        "min_window_seconds": args.min_window_seconds
        or metadata.get("production_min_window_seconds")
        or 2.0,
        "variable_windows": not args.no_variable_windows
        and bool(metadata.get("production_variable_windows", True)),
        "adaptive_short_video_windows": not args.no_adaptive_short_videos
        and bool(metadata.get("production_adaptive_short_video_windows", True)),
        "stride_seconds": args.stride_seconds or metadata.get("production_stride_seconds") or 1.0,
        "threshold": args.threshold if args.threshold is not None else metadata.get("threshold", 0.75),
        "smoothing_window": args.smoothing_window or metadata.get("production_smoothing_window") or 5,
        "min_consecutive_hits": args.min_consecutive_hits
        or metadata.get("production_min_consecutive_hits")
        or 2,
        "alert_mode": args.alert_mode or metadata.get("production_alert_mode") or "consecutive_or_average",
        "alert_cooldown_seconds": args.alert_cooldown_seconds
        if args.alert_cooldown_seconds is not None
        else metadata.get("production_alert_cooldown_seconds", 0.0),
    }

    videos = iter_videos(Path(args.input))
    if args.max_videos > 0:
        videos = videos[: args.max_videos]
    if not videos:
        raise RuntimeError(f"Nenhum video encontrado em: {args.input}")

    classifier = FallClassifier(checkpoint, device=args.device)
    all_mined = []
    summaries = []
    for index, video_path in enumerate(videos, start=1):
        mined, summary = run_video(
            video_path,
            classifier,
            config,
            args.dataset,
            args.min_hard_negative_probability,
            args.max_duration_seconds,
        )
        all_mined.extend(mined)
        summaries.append(summary)
        print(f"{index}/{len(videos)} {video_path} alerts={summary.get('alert_events', 0)} mined={len(mined)}", flush=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        for row in sorted(all_mined, key=lambda item: item["fall_probability"], reverse=True):
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    total_seconds = sum(float(row.get("duration_seconds") or 0.0) for row in summaries)
    total_alerts = sum(int(row.get("alert_events") or 0) for row in summaries)
    report = {
        "checkpoint": str(checkpoint),
        "input": args.input,
        "config": config,
        "videos": len(videos),
        "total_duration_seconds": total_seconds,
        "total_negative_hours": total_seconds / 3600.0,
        "alert_events": total_alerts,
        "false_alerts_per_hour": 0.0 if total_seconds <= 0 else total_alerts / (total_seconds / 3600.0),
        "mined_windows": len(all_mined),
        "per_video": summaries,
        "output": str(output_path),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
