import argparse
import pickle
from pathlib import Path

import cv2
import numpy as np
import torch
from transformers import AutoModel, AutoVideoProcessor

from predict_fall_video import aggregate_fall_probability, iter_windows
from train_fall_classifier import (
    CLASS_NAMES,
    CLASS_TO_ID,
    DEFAULT_MODEL_NAME,
    get_torch_device,
    get_video_frame_count,
    log,
    read_video_frames_opencv,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Roda inferencia de queda em video usando classificador sobre embeddings V-JEPA 2."
    )
    parser.add_argument("--video", required=True)
    parser.add_argument("--checkpoint", default="best_fall_embedding_classifier.pkl")
    parser.add_argument("--window-seconds", type=float, default=2.5)
    parser.add_argument("--stride-seconds", type=float, default=0.75)
    parser.add_argument("--num-frames", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--aggregation", choices=["max", "topk_mean", "mean"], default="topk_mean")
    parser.add_argument("--topk", type=int, default=3)
    parser.add_argument("--start-frame", type=int, default=None)
    parser.add_argument("--end-frame", type=int, default=None)
    return parser.parse_args()


def get_video_fps(video_path: Path) -> float:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Nao foi possivel abrir o video: {video_path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    cap.release()
    return fps if fps > 0 else 30.0


@torch.no_grad()
def embed_window(model, processor, video_path: Path, start_frame: int, end_frame: int, num_frames: int, device: str):
    frames = read_video_frames_opencv(
        str(video_path),
        num_frames=num_frames,
        start_frame=start_frame,
        end_frame=end_frame,
    )
    inputs = processor(frames, return_tensors="pt")
    pixel_values = inputs["pixel_values_videos"].to(device)
    outputs = model(pixel_values_videos=pixel_values, skip_predictor=True)
    tokens = outputs.last_hidden_state
    features = torch.cat([tokens.mean(dim=1), tokens.max(dim=1).values], dim=1)
    return features.cpu().numpy().astype(np.float32)


def predict_fall_prob(classifier, features):
    if hasattr(classifier, "predict_proba"):
        return float(classifier.predict_proba(features)[0, CLASS_TO_ID["queda"]])
    score = classifier.decision_function(features)[0]
    return float(1.0 / (1.0 + np.exp(-score)))


def main():
    args = parse_args()
    video_path = Path(args.video)
    checkpoint_path = Path(args.checkpoint)
    if not video_path.exists():
        raise FileNotFoundError(f"Video nao encontrado: {video_path}")
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint nao encontrado: {checkpoint_path}")

    with checkpoint_path.open("rb") as f:
        payload = pickle.load(f)
    classifier = payload["model"]
    metadata = payload["metadata"]
    model_name = metadata.get("backbone") or DEFAULT_MODEL_NAME
    num_frames = args.num_frames or int(metadata.get("num_frames") or 16)
    args.num_frames = num_frames
    threshold = args.threshold if args.threshold is not None else float(metadata.get("threshold") or 0.6)

    device = get_torch_device()
    log(f"Usando device: {device}")
    processor = AutoVideoProcessor.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name).to(device)
    model.eval()

    window_results = []
    for start_frame, end_frame in iter_windows(video_path, args):
        features = embed_window(model, processor, video_path, start_frame, end_frame, num_frames, device)
        fall_prob = predict_fall_prob(classifier, features)
        window_results.append(
            {
                "start_frame": start_frame,
                "end_frame": end_frame,
                "fall_prob": fall_prob,
            }
        )

    fall_probs = [item["fall_prob"] for item in window_results]
    aggregated = aggregate_fall_probability(fall_probs, args.aggregation, args.topk)
    pred_name = "queda" if aggregated >= threshold else "sem_queda"
    best_window = max(window_results, key=lambda item: item["fall_prob"])

    print("\n=== Prediction ===", flush=True)
    print(f"classe_predita: {pred_name}", flush=True)
    print(f"queda_agregada: {aggregated:.4f}", flush=True)
    print(f"threshold: {threshold:.4f}", flush=True)
    print(f"classifier: {metadata.get('classifier')}", flush=True)
    print(f"janelas_avaliadas: {len(window_results)}", flush=True)
    print(
        "melhor_janela: "
        f"{best_window['start_frame']}-{best_window['end_frame']} "
        f"queda={best_window['fall_prob']:.4f}",
        flush=True,
    )
    print("\n=== Top windows ===", flush=True)
    for item in sorted(window_results, key=lambda value: value["fall_prob"], reverse=True)[: args.topk]:
        print(f"{item['start_frame']}-{item['end_frame']}: queda={item['fall_prob']:.4f}", flush=True)


if __name__ == "__main__":
    main()
