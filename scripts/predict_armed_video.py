"""Inspeciona o checkpoint de armas em um video local, sem disparar notificacoes."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fall_detection.armed_inference import ArmedClassifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--checkpoint", default="fall_detection/models/best_gun_binary_classifier_head.pt")
    parser.add_argument("--device", default=None)
    parser.add_argument("--sliding-windows", action="store_true")
    parser.add_argument("--stride-seconds", type=float, default=1.0)
    args = parser.parse_args()
    classifier = ArmedClassifier(args.checkpoint, device=args.device)
    if args.sliding_windows:
        result = classifier.predict_video_windows(args.source, stride_seconds=args.stride_seconds)
    else:
        # Janela inicial com a duracao do treino; janelas deslizantes analisam todo o video.
        import cv2

        cap = cv2.VideoCapture(args.source)
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
        finally:
            cap.release()
        if fps <= 0:
            raise ValueError("Nao foi possivel determinar o FPS do video.")
        result = classifier.predict_video_file(
            args.source, start_frame=0, end_frame=round(classifier.view_duration_seconds * fps),
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
