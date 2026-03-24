import argparse
from pathlib import Path

import torch
from transformers import AutoVideoProcessor

from train_fall_classifier import (
    CLASS_NAMES,
    MODEL_NAME,
    VJEPA2Classifier,
    log,
    read_video_frames_opencv,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Roda inferencia de queda em um video usando o checkpoint treinado."
    )
    parser.add_argument("--video", required=True, help="Caminho para o video.")
    parser.add_argument(
        "--checkpoint",
        default="best_vjepa2_fall_classifier.pt",
        help="Checkpoint treinado salvo pelo script de treino.",
    )
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--start-frame", type=int, default=None)
    parser.add_argument("--end-frame", type=int, default=None)
    return parser.parse_args()


@torch.no_grad()
def main():
    args = parse_args()
    video_path = Path(args.video)
    checkpoint_path = Path(args.checkpoint)

    if not video_path.exists():
        raise FileNotFoundError(f"Video nao encontrado: {video_path}")
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint nao encontrado: {checkpoint_path}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log(f"Usando device: {device}")
    log(f"Video: {video_path}")
    log(f"Checkpoint: {checkpoint_path}")

    log(f"Carregando processor do modelo: {MODEL_NAME}")
    processor = AutoVideoProcessor.from_pretrained(MODEL_NAME)

    log("Lendo frames do video.")
    frames = read_video_frames_opencv(
        str(video_path),
        num_frames=args.num_frames,
        start_frame=args.start_frame,
        end_frame=args.end_frame,
    )

    log("Processando frames.")
    inputs = processor(frames, return_tensors="pt")
    pixel_values_videos = inputs["pixel_values_videos"].to(device)

    log("Carregando modelo.")
    model = VJEPA2Classifier(
        model_name=MODEL_NAME,
        num_classes=len(CLASS_NAMES),
        freeze_backbone=True,
    ).to(device)
    state_dict = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    log("Rodando inferencia.")
    logits = model(pixel_values_videos)
    probs = torch.softmax(logits, dim=1).squeeze(0).cpu().tolist()
    pred_idx = int(torch.argmax(logits, dim=1).item())

    print("\n=== Prediction ===", flush=True)
    print(f"classe_predita: {CLASS_NAMES[pred_idx]}", flush=True)
    for class_name, prob in zip(CLASS_NAMES, probs):
        print(f"{class_name}: {prob:.4f}", flush=True)


if __name__ == "__main__":
    main()
