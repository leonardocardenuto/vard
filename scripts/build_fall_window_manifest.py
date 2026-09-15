from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2

CLASS_NAMES = ["sem_queda", "queda"]
CLASS_TO_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


@dataclass(frozen=True)
class VideoSample:
    video_path: str
    label: int
    start_frame: int | None = None
    end_frame: int | None = None
    group_id: str | None = None


def log(message: str):
    print(message, flush=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Gera um manifesto de janelas temporais com overlap para deteccao de queda."
    )
    parser.add_argument(
        "--local-dataset",
        required=True,
        help="Raiz local do MCFD, ou pasta pai contendo data_tuple3.csv e os videos.",
    )
    parser.add_argument("--dataset-name", default="mcfd")
    parser.add_argument("--window-seconds", type=float, default=30.0)
    parser.add_argument("--stride-seconds", type=float, default=10.0)
    parser.add_argument("--positive-overlap-seconds", type=float, default=1.0)
    parser.add_argument("--context-before-seconds", type=float, default=2.0)
    parser.add_argument("--context-after-seconds", type=float, default=3.0)
    parser.add_argument(
        "--negative-context-seconds",
        type=float,
        default=None,
        help=(
            "Duracao de contexto adicionada a cada lado das anotacoes sem queda no modo "
            "annotation-context. Por padrao usa a media de before/after."
        ),
    )
    parser.add_argument(
        "--negative-fall-margin-seconds",
        type=float,
        default=0.0,
        help=(
            "No modo annotation-context, remove janelas sem queda que ficam a menos desta "
            "distancia de uma queda anotada no mesmo video."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("sliding", "annotation", "annotation-context"),
        default="sliding",
        help=(
            "sliding cria janelas com overlap no video inteiro; annotation cria uma janela "
            "centrada em cada anotacao do CSV; annotation-context expande cada anotacao com "
            "contexto antes/depois e permite janelas de duracao variavel."
        ),
    )
    parser.add_argument("--output", default="fall_windows_mcfd_30s_10s.jsonl")
    return parser.parse_args()


def get_video_info(video_path: Path) -> tuple[float, int, float]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()

    if fps <= 0:
        fps = 30.0
    if frame_count <= 0:
        raise RuntimeError(f"Video sem frames validos: {video_path}")

    return fps, frame_count, frame_count / fps


def find_dataset_root(download_dir: Path) -> Path:
    directories_with_videos = {}
    for video_path in download_dir.rglob("*"):
        if video_path.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        parent = video_path.parent
        directories_with_videos[parent] = directories_with_videos.get(parent, 0) + 1

    if not directories_with_videos:
        raise RuntimeError("Nenhum video encontrado no dataset.")

    best_root = max(
        directories_with_videos,
        key=lambda path: (len(path.relative_to(download_dir).parts), directories_with_videos[path]),
    )
    return best_root.parent if best_root.name.startswith("chute") else best_root


def find_metadata_csv(dataset_path: Path) -> Path | None:
    preferred = [
        dataset_path / "data_tuple3.csv",
        dataset_path.parent / "data_tuple3.csv",
    ]
    for candidate in preferred:
        if candidate.exists():
            return candidate

    matches = list(dataset_path.rglob("data_tuple3.csv"))
    if matches:
        return matches[0]
    return None


def normalize_mcfd_cam(chute: int, cam_raw: str, start_frame: int, end_frame: int) -> int:
    cam = int(float(cam_raw))
    if 1 <= cam <= 8:
        return cam

    if chute == 23 and cam == 55 and start_frame == 1572 and end_frame == 1602:
        log("Corrigindo typo conhecido do CSV: chute23 cam55 -> cam3")
        return 3

    raise ValueError(
        f"Valor de camera invalido no CSV: chute={chute} cam={cam_raw} start={start_frame} end={end_frame}"
    )


def load_mcfd_samples(dataset_root: Path, metadata_path: Path) -> list[VideoSample]:
    samples = []
    with metadata_path.open() as metadata_file:
        reader = csv.DictReader(metadata_file)
        for row in reader:
            chute = int(float(row["chute"]))
            start_frame = int(float(row["start"]))
            end_frame = int(float(row["end"]))
            cam = normalize_mcfd_cam(chute, row["cam"], start_frame, end_frame)
            label = int(float(row["label"]))

            video_path = dataset_root / f"chute{chute:02d}" / f"cam{cam}.avi"
            if not video_path.exists():
                raise FileNotFoundError(f"Video anotado nao encontrado: {video_path}")

            samples.append(
                VideoSample(
                    video_path=str(video_path),
                    label=label,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    group_id=f"chute{chute:02d}",
                )
            )
    log(f"Amostras anotadas carregadas do CSV: {len(samples)}")
    return samples


def frame_overlap_seconds(
    window_start: int,
    window_end: int,
    fall_start: int,
    fall_end: int,
    fps: float,
) -> float:
    overlap_start = max(window_start, fall_start)
    overlap_end = min(window_end, fall_end)
    if overlap_end < overlap_start:
        return 0.0
    return (overlap_end - overlap_start + 1) / fps


def iter_window_bounds(frame_count: int, fps: float, window_seconds: float, stride_seconds: float):
    window_frames = max(1, int(round(window_seconds * fps)))
    stride_frames = max(1, int(round(stride_seconds * fps)))

    if frame_count <= window_frames:
        yield 0, frame_count - 1
        return

    start = 0
    while start + window_frames <= frame_count:
        yield start, start + window_frames - 1
        start += stride_frames

    last_start = max(0, frame_count - window_frames)
    if last_start > 0 and last_start != start - stride_frames:
        yield last_start, frame_count - 1


def annotation_window_bounds(
    annotation_start: int,
    annotation_end: int,
    frame_count: int,
    fps: float,
    window_seconds: float,
) -> tuple[int, int]:
    window_frames = min(frame_count, max(1, int(round(window_seconds * fps))))
    center = int(round((annotation_start + annotation_end) / 2))
    start = max(0, center - window_frames // 2)
    end = min(frame_count - 1, start + window_frames - 1)
    start = max(0, end - window_frames + 1)
    return start, end


def annotation_context_window_bounds(
    sample: VideoSample,
    fall_intervals: list[VideoSample],
    frame_count: int,
    fps: float,
    context_before_seconds: float,
    context_after_seconds: float,
    negative_context_seconds: float,
) -> tuple[int, int]:
    if sample.start_frame is None or sample.end_frame is None:
        raise ValueError("Amostra sem intervalo anotado.")

    if sample.label == CLASS_TO_ID["queda"]:
        before_frames = int(round(context_before_seconds * fps))
        after_frames = int(round(context_after_seconds * fps))
        start = sample.start_frame - before_frames
        end = sample.end_frame + after_frames
    else:
        context_frames = int(round(negative_context_seconds * fps))
        start = sample.start_frame - context_frames
        end = sample.end_frame + context_frames
        for fall_sample in fall_intervals:
            if fall_sample.start_frame is None or fall_sample.end_frame is None:
                continue
            if fall_sample.end_frame < sample.start_frame:
                start = max(start, fall_sample.end_frame + 1)
            elif fall_sample.start_frame > sample.end_frame:
                end = min(end, fall_sample.start_frame - 1)
            elif fall_sample.start_frame <= sample.end_frame and fall_sample.end_frame >= sample.start_frame:
                start = sample.start_frame
                end = sample.end_frame
                break

    start = max(0, start)
    end = min(frame_count - 1, end)
    if end < start:
        return sample.start_frame, sample.end_frame
    return start, end


def build_record(
    args,
    video_path: Path,
    group_id: str,
    window_index: int,
    start_frame: int,
    end_frame: int,
    sample: VideoSample,
    fall_overlap: float,
    fps: float,
    frame_count: int,
    duration_seconds: float,
) -> dict:
    annotation_duration_seconds = 0.0
    if sample.start_frame is not None and sample.end_frame is not None:
        annotation_duration_seconds = (sample.end_frame - sample.start_frame + 1) / fps

    return {
        "video_path": str(video_path),
        "dataset": args.dataset_name,
        "group_id": group_id,
        "window_index": window_index,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "annotation_start_frame": sample.start_frame,
        "annotation_end_frame": sample.end_frame,
        "start_time": start_frame / fps,
        "end_time": min(duration_seconds, (end_frame + 1) / fps),
        "window_duration_seconds": (end_frame - start_frame + 1) / fps,
        "annotation_duration_seconds": annotation_duration_seconds,
        "label": CLASS_NAMES[sample.label],
        "label_id": sample.label,
        "fall_overlap_seconds": fall_overlap,
        "fps": fps,
        "frame_count": frame_count,
        "window_seconds": args.window_seconds,
        "stride_seconds": args.stride_seconds,
        "positive_overlap_seconds": args.positive_overlap_seconds,
        "context_before_seconds": args.context_before_seconds,
        "context_after_seconds": args.context_after_seconds,
        "negative_context_seconds": args.negative_context_seconds,
        "negative_fall_margin_seconds": args.negative_fall_margin_seconds,
        "manifest_mode": args.mode,
        "class_names": CLASS_NAMES,
    }


def seconds_to_nearest_fall(
    start_frame: int,
    end_frame: int,
    fall_intervals: list[VideoSample],
    fps: float,
) -> float | None:
    nearest = None
    for fall_sample in fall_intervals:
        if fall_sample.start_frame is None or fall_sample.end_frame is None:
            continue
        if end_frame < fall_sample.start_frame:
            distance_frames = fall_sample.start_frame - end_frame - 1
        elif start_frame > fall_sample.end_frame:
            distance_frames = start_frame - fall_sample.end_frame - 1
        else:
            distance_frames = 0
        distance_seconds = max(0.0, distance_frames / fps)
        nearest = distance_seconds if nearest is None else min(nearest, distance_seconds)
    return nearest


def resolve_mcfd(dataset_path: Path):
    metadata_path = find_metadata_csv(dataset_path)
    dataset_root = dataset_path

    if metadata_path is None or not any(dataset_root.glob("chute*/cam*.avi")):
        dataset_root = find_dataset_root(dataset_path)
        metadata_path = find_metadata_csv(dataset_path) or find_metadata_csv(dataset_root)

    if metadata_path is None:
        raise FileNotFoundError(
            "CSV data_tuple3.csv nao encontrado. Este script espera o MCFD com anotacoes temporais."
        )

    return dataset_root, metadata_path


def main():
    args = parse_args()
    if args.window_seconds <= 0:
        raise ValueError("--window-seconds deve ser maior que zero.")
    if args.stride_seconds <= 0:
        raise ValueError("--stride-seconds deve ser maior que zero.")
    if args.positive_overlap_seconds <= 0:
        raise ValueError("--positive-overlap-seconds deve ser maior que zero.")
    if args.context_before_seconds < 0 or args.context_after_seconds < 0:
        raise ValueError("Contextos antes/depois nao podem ser negativos.")
    if args.negative_context_seconds is None:
        args.negative_context_seconds = (args.context_before_seconds + args.context_after_seconds) / 2
    if args.negative_context_seconds < 0:
        raise ValueError("--negative-context-seconds nao pode ser negativo.")
    if args.negative_fall_margin_seconds < 0:
        raise ValueError("--negative-fall-margin-seconds nao pode ser negativo.")

    dataset_path = Path(args.local_dataset)
    output_path = Path(args.output)
    dataset_root, metadata_path = resolve_mcfd(dataset_path)
    log(f"Dataset root: {dataset_root}")
    log(f"Metadata CSV: {metadata_path}")

    samples = load_mcfd_samples(dataset_root, metadata_path)
    fall_samples_by_video = defaultdict(list)
    samples_by_video = defaultdict(list)
    group_by_video = {}
    for sample in samples:
        video_path = str(Path(sample.video_path).resolve())
        group_by_video[video_path] = sample.group_id or video_path
        samples_by_video[video_path].append(sample)
        if sample.label == CLASS_TO_ID["queda"]:
            fall_samples_by_video[video_path].append(sample)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    ignored_ambiguous = 0
    total_duration_seconds = 0.0

    with output_path.open("w", encoding="utf-8") as output_file:
        for video_path_text in sorted(group_by_video):
            video_path = Path(video_path_text)
            fps, frame_count, duration_seconds = get_video_info(video_path)
            total_duration_seconds += duration_seconds
            fall_intervals = fall_samples_by_video.get(video_path_text, [])
            if args.mode in ("annotation", "annotation-context"):
                for window_index, sample in enumerate(samples_by_video[video_path_text]):
                    if sample.start_frame is None or sample.end_frame is None:
                        continue
                    if args.mode == "annotation-context":
                        start_frame, end_frame = annotation_context_window_bounds(
                            sample,
                            fall_intervals,
                            frame_count,
                            fps,
                            args.context_before_seconds,
                            args.context_after_seconds,
                            args.negative_context_seconds,
                        )
                    else:
                        start_frame, end_frame = annotation_window_bounds(
                            sample.start_frame,
                            sample.end_frame,
                            frame_count,
                            fps,
                            args.window_seconds,
                        )
                    fall_overlap = 0.0
                    for fall_sample in fall_intervals:
                        if fall_sample.start_frame is None or fall_sample.end_frame is None:
                            continue
                        fall_overlap += frame_overlap_seconds(
                            start_frame,
                            end_frame,
                            fall_sample.start_frame,
                            fall_sample.end_frame,
                            fps,
                        )

                    if sample.label == CLASS_TO_ID["sem_queda"] and fall_overlap > 0:
                        ignored_ambiguous += 1
                        continue
                    nearest_fall_seconds = seconds_to_nearest_fall(
                        start_frame,
                        end_frame,
                        fall_intervals,
                        fps,
                    )
                    if (
                        sample.label == CLASS_TO_ID["sem_queda"]
                        and nearest_fall_seconds is not None
                        and nearest_fall_seconds < args.negative_fall_margin_seconds
                    ):
                        ignored_ambiguous += 1
                        continue

                    counts[CLASS_NAMES[sample.label]] += 1
                    record = build_record(
                        args,
                        video_path,
                        group_by_video[video_path_text],
                        window_index,
                        start_frame,
                        end_frame,
                        sample,
                        fall_overlap,
                        fps,
                        frame_count,
                        duration_seconds,
                    )
                    record["seconds_to_nearest_fall"] = nearest_fall_seconds
                    output_file.write(json.dumps(record, ensure_ascii=True) + "\n")
                continue

            for window_index, (start_frame, end_frame) in enumerate(
                iter_window_bounds(frame_count, fps, args.window_seconds, args.stride_seconds)
            ):
                fall_overlap = 0.0
                for fall_sample in fall_intervals:
                    if fall_sample.start_frame is None or fall_sample.end_frame is None:
                        continue
                    fall_overlap += frame_overlap_seconds(
                        start_frame,
                        end_frame,
                        fall_sample.start_frame,
                        fall_sample.end_frame,
                        fps,
                    )

                if fall_overlap >= args.positive_overlap_seconds:
                    label = "queda"
                elif fall_overlap == 0:
                    label = "sem_queda"
                else:
                    ignored_ambiguous += 1
                    continue

                counts[label] += 1
                record = {
                    "video_path": str(video_path),
                    "dataset": args.dataset_name,
                    "group_id": group_by_video[video_path_text],
                    "window_index": window_index,
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "start_time": start_frame / fps,
                    "end_time": min(duration_seconds, (end_frame + 1) / fps),
                    "label": label,
                    "label_id": CLASS_TO_ID[label],
                    "fall_overlap_seconds": fall_overlap,
                    "fps": fps,
                    "frame_count": frame_count,
                    "window_seconds": args.window_seconds,
                    "stride_seconds": args.stride_seconds,
                    "positive_overlap_seconds": args.positive_overlap_seconds,
                    "manifest_mode": args.mode,
                    "class_names": CLASS_NAMES,
                }
                output_file.write(json.dumps(record, ensure_ascii=True) + "\n")

    log(f"Manifesto salvo em: {output_path}")
    log(f"Janelas por classe: {dict(counts)}")
    log(f"Janelas ambiguas ignoradas: {ignored_ambiguous}")
    log(f"Duracao total aproximada: {total_duration_seconds / 60:.2f} minutos")


if __name__ == "__main__":
    main()
