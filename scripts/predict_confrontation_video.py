"""Classifica um video local como confronto/nao_confronto, sem banco ou push."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2

from fall_detection.confrontation_inference import ConfrontationClassifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--checkpoint", default="fall_detection/models/best_confrontation_classifier_head.pt")
    parser.add_argument("--device", default=None)
    parser.add_argument("--sliding-windows", action="store_true")
    parser.add_argument("--stride-seconds", type=float, default=1.0)
    args = parser.parse_args()
    classifier = ConfrontationClassifier(args.checkpoint, device=args.device)
    if args.sliding_windows:
        results = classifier.predict_video_windows(args.source, stride_seconds=args.stride_seconds)
    else:
        cap = cv2.VideoCapture(args.source)
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        finally:
            cap.release()
        if fps <= 0 or total_frames < classifier.num_frames:
            raise ValueError("Video ilegivel ou sem frames suficientes.")
        if total_frames / fps < classifier.view_duration_seconds * 0.9:
            raise ValueError("Video curto demais para a janela temporal do checkpoint.")
        results = [classifier.predict_video_file(
            args.source, start_frame=0,
            end_frame=min(total_frames - 1, round(classifier.view_duration_seconds * fps) - 1),
        )]
    print(json.dumps({"checkpoint": str(classifier.checkpoint),
                      "recommended_threshold": classifier.recommended_threshold,
                      "windows": results}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
