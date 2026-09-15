from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fall_detection.inference import CLASS_TO_ID, FallClassifier


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extrai features exatamente como o checkpoint de producao espera, a partir de um manifesto."
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--checkpoint", default="var/best_vjepa2_fall_classifier_combined.pt")
    parser.add_argument("--output", required=True)
    parser.add_argument("--sample-fps", type=float, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--max-windows", type=int, default=0)
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


def read_window_frames(row: dict, sample_fps: float, min_frames: int) -> list[np.ndarray]:
    cap = cv2.VideoCapture(row["video_path"])
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir video: {row['video_path']}")
    fps = float(row.get("fps") or cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if fps <= 0:
        fps = 30.0
    start_frame = int(row["start_frame"])
    end_frame = int(row["end_frame"])
    duration = max(0.0, (end_frame - start_frame + 1) / fps)
    frame_count = max(min_frames, int(round(duration * sample_fps)))
    indices = np.linspace(start_frame, end_frame, frame_count).astype(int).tolist()
    frames = []
    for frame_index in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame_bgr = cap.read()
        if not ok:
            continue
        frames.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    cap.release()
    if not frames:
        raise RuntimeError(f"Nenhum frame lido para janela: {row['video_path']} {start_frame}-{end_frame}")
    while len(frames) < min_frames:
        frames.append(frames[-1])
    return frames


def extract_features(classifier: FallClassifier, frames: list[np.ndarray], sample_fps: float) -> np.ndarray:
    if classifier.model_type != "vjepa2_window_embedding_sklearn":
        return classifier._embed_frame_clip(frames).squeeze(0)
    features = classifier._embed_frame_window(frames, sample_fps=sample_fps)
    if classifier.auxiliary_yolo is not None:
        features = np.concatenate([features, classifier._extract_auxiliary_yolo_features(frames)], axis=1)
    if classifier.auxiliary_pose is not None:
        features = np.concatenate([features, classifier._extract_auxiliary_pose_features(frames)], axis=1)
    return features.squeeze(0).astype(np.float32)


def main():
    args = parse_args()
    rows = load_manifest(Path(args.manifest))
    if args.max_windows > 0:
        rows = rows[: args.max_windows]

    classifier = FallClassifier(args.checkpoint, device=args.device)
    metadata = classifier.embedding_metadata or {}
    sample_fps = float(args.sample_fps or metadata.get("production_sample_fps") or 6.0)

    features = []
    labels = []
    kept_rows = []
    for index, row in enumerate(rows, start=1):
        frames = read_window_frames(row, sample_fps=sample_fps, min_frames=classifier.num_frames)
        features.append(extract_features(classifier, frames, sample_fps=sample_fps))
        labels.append(CLASS_TO_ID[row["label"]])
        kept_rows.append(row)
        if index == 1 or index % 10 == 0 or index == len(rows):
            print(f"features {index}/{len(rows)}", flush=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        x=np.stack(features).astype(np.float32),
        y=np.array(labels, dtype=np.int64),
        metadata=json.dumps(
            {
                "manifest": args.manifest,
                "checkpoint": args.checkpoint,
                "sample_fps": sample_fps,
                "feature_source": "checkpoint_runtime",
                "rows": len(kept_rows),
            }
        ),
    )
    print(f"Features salvas em: {output_path}")


if __name__ == "__main__":
    main()
