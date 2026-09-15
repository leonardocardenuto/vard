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

from fall_detection.person_masked_bag import PersonSegmenter, load_jsonl, read_video_segment_frames, sample_items


def parse_args():
    parser = argparse.ArgumentParser(description="Gera contact sheet de frames originais vs mascarados por YOLO-seg.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default="artifacts/reports/person_mask_contact_sheet.jpg")
    parser.add_argument("--person-seg-model", default="yolo11n-seg.pt")
    parser.add_argument("--person-seg-confidence", type=float, default=0.25)
    parser.add_argument("--sample-fps", type=float, default=6.0)
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--frames-per-row", type=int, default=3)
    parser.add_argument("--thumb-width", type=int, default=180)
    parser.add_argument("--device", default=None)
    return parser.parse_args()


def resize_rgb(frame: np.ndarray, width: int) -> np.ndarray:
    height, current_width = frame.shape[:2]
    new_height = max(1, int(round(height * (width / max(1, current_width)))))
    return cv2.resize(frame, (width, new_height), interpolation=cv2.INTER_AREA)


def add_label(frame_rgb: np.ndarray, text: str) -> np.ndarray:
    frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
    overlay = frame_bgr.copy()
    cv2.rectangle(overlay, (0, 0), (frame_bgr.shape[1], 24), (0, 0, 0), -1)
    frame_bgr = cv2.addWeighted(overlay, 0.55, frame_bgr, 0.45, 0)
    cv2.putText(frame_bgr, text[:60], (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)


def pad_to_height(frame: np.ndarray, height: int) -> np.ndarray:
    if frame.shape[0] == height:
        return frame
    pad = np.zeros((height - frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
    return np.concatenate([frame, pad], axis=0)


def main():
    args = parse_args()
    rows = load_jsonl(args.manifest)[: args.rows]
    segmenter = PersonSegmenter(
        model_path=args.person_seg_model,
        confidence=args.person_seg_confidence,
        background_mode="mask_black",
        no_person_policy="original",
        device=args.device,
    )

    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        frames = read_video_segment_frames(
            row["video_path"],
            sample_fps=args.sample_fps,
            start_frame=row.get("start_frame"),
            end_frame=row.get("end_frame"),
        )
        selected = sample_items(frames, args.frames_per_row)
        cells = []
        for frame_index, frame in enumerate(selected, start=1):
            masked = segmenter.apply(frame)
            original_thumb = add_label(
                resize_rgb(frame, args.thumb_width),
                f"{row.get('label')} r{row_index}.{frame_index} original",
            )
            masked_thumb = add_label(
                resize_rgb(masked.frame, args.thumb_width),
                f"mask area={masked.stats[2]:.3f} conf={masked.stats[1]:.2f}",
            )
            target_h = max(original_thumb.shape[0], masked_thumb.shape[0])
            cells.extend([pad_to_height(original_thumb, target_h), pad_to_height(masked_thumb, target_h)])
        row_h = max(cell.shape[0] for cell in cells)
        sheet_rows.append(np.concatenate([pad_to_height(cell, row_h) for cell in cells], axis=1))

    target_w = max(row.shape[1] for row in sheet_rows)
    padded_rows = []
    for row in sheet_rows:
        if row.shape[1] < target_w:
            pad = np.zeros((row.shape[0], target_w - row.shape[1], 3), dtype=np.uint8)
            row = np.concatenate([row, pad], axis=1)
        padded_rows.append(row)
    sheet = np.concatenate(padded_rows, axis=0)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    print(json.dumps({"output": str(output_path), "rows": len(rows)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
