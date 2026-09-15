from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from sklearn.model_selection import GroupShuffleSplit


def parse_args():
    parser = argparse.ArgumentParser(
        description="Cria dataset YOLO-OBB pseudo-rotulado com caixas de pessoa para treinar auxiliar espacial."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-dir", default="artifacts/yolo_obb_pseudo_mcfd")
    parser.add_argument("--teacher-model", default="yolo11n.pt")
    parser.add_argument("--frames-per-window", type=int, default=2)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-windows", type=int, default=0)
    parser.add_argument("--device", default=None)
    parser.add_argument("--clean", action="store_true")
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as manifest_file:
        for line in manifest_file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        raise RuntimeError(f"Manifesto vazio: {path}")
    return rows


def split_rows(rows: list[dict], val_size: float, seed: int):
    labels = np.array([int(row["label_id"]) for row in rows], dtype=np.int64)
    groups = np.array([row.get("group_id") or row["video_path"] for row in rows])
    splitter = GroupShuffleSplit(n_splits=50, test_size=val_size, random_state=seed)
    for train_idx, val_idx in splitter.split(rows, labels, groups):
        if len(set(labels[train_idx])) == 2 and len(set(labels[val_idx])) == 2:
            return train_idx, val_idx
    raise RuntimeError("Nao consegui split agrupado com as duas classes.")


def sample_frame_indices(start_frame: int, end_frame: int, count: int) -> list[int]:
    if count <= 1:
        return [start_frame]
    return np.linspace(start_frame, end_frame, count).astype(int).tolist()


def read_frame(video_path: str, frame_index: int):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir video: {video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame_bgr = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Nao foi possivel ler frame {frame_index}: {video_path}")
    return frame_bgr


def xyxy_to_obb_line(box, image_width: int, image_height: int) -> str:
    x1, y1, x2, y2 = [float(value) for value in box]
    x1 = max(0.0, min(float(image_width - 1), x1))
    x2 = max(0.0, min(float(image_width - 1), x2))
    y1 = max(0.0, min(float(image_height - 1), y1))
    y2 = max(0.0, min(float(image_height - 1), y2))
    if x2 <= x1 or y2 <= y1:
        return ""
    points = [
        x1 / image_width,
        y1 / image_height,
        x2 / image_width,
        y1 / image_height,
        x2 / image_width,
        y2 / image_height,
        x1 / image_width,
        y2 / image_height,
    ]
    return "0 " + " ".join(f"{value:.6f}" for value in points)


def write_dataset_yaml(output_dir: Path):
    yaml_path = output_dir / "dataset.yaml"
    yaml_path.write_text(
        "\n".join(
            [
                f"path: {output_dir.resolve()}",
                "train: images/train",
                "val: images/val",
                "names:",
                "  0: person",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return yaml_path


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)

    rows = load_manifest(Path(args.manifest))
    if args.max_windows > 0:
        rows = rows[: args.max_windows]
    train_idx, val_idx = split_rows(rows, args.val_size, args.seed)
    split_by_index = {int(index): "train" for index in train_idx}
    split_by_index.update({int(index): "val" for index in val_idx})

    for split in ("train", "val"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Instale ultralytics: pip install -r requirements-ml.txt") from exc

    teacher = YOLO(args.teacher_model)
    stats = defaultdict(int)
    for row_index, row in enumerate(rows):
        split = split_by_index[row_index]
        for frame_index in sample_frame_indices(
            int(row["start_frame"]),
            int(row["end_frame"]),
            args.frames_per_window,
        ):
            try:
                frame_bgr = read_frame(row["video_path"], frame_index)
            except RuntimeError:
                stats["read_errors"] += 1
                continue
            height, width = frame_bgr.shape[:2]
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            result = teacher.predict(
                frame_rgb,
                classes=[0],
                conf=args.confidence,
                verbose=False,
                device=args.device,
            )[0]
            lines = []
            if result.boxes is not None and len(result.boxes) > 0:
                xyxy = result.boxes.xyxy.detach().cpu().numpy()
                confs = result.boxes.conf.detach().cpu().numpy()
                for box, conf in sorted(zip(xyxy, confs), key=lambda item: float(item[1]), reverse=True)[:3]:
                    line = xyxy_to_obb_line(box, width, height)
                    if line:
                        lines.append(line)

            if not lines:
                stats["empty_labels"] += 1
                continue

            stem = f"row{row_index:05d}_frame{frame_index:06d}"
            image_path = output_dir / "images" / split / f"{stem}.jpg"
            label_path = output_dir / "labels" / split / f"{stem}.txt"
            cv2.imwrite(str(image_path), frame_bgr)
            label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            stats[f"{split}_images"] += 1
            stats["boxes"] += len(lines)

        if row_index == 0 or (row_index + 1) % 50 == 0 or row_index + 1 == len(rows):
            print(f"pseudo dataset {row_index + 1}/{len(rows)}", flush=True)

    yaml_path = write_dataset_yaml(output_dir)
    report = {
        "manifest": args.manifest,
        "output_dir": str(output_dir),
        "dataset_yaml": str(yaml_path),
        "teacher_model": args.teacher_model,
        "frames_per_window": args.frames_per_window,
        "confidence": args.confidence,
        "stats": dict(stats),
    }
    report_path = output_dir / "pseudo_label_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
