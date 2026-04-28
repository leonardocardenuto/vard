import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fall_detection import CameraWorker, FrameBuffer


def parse_args():
    parser = argparse.ArgumentParser(
        description="Smoke test leve para captura, buffer circular e amostragem usando um video local."
    )
    parser.add_argument("--source", required=True, help="Caminho para video local.")
    parser.add_argument("--num-frames", type=int, default=16)
    parser.add_argument("--sample-fps", type=float, default=6.0)
    parser.add_argument("--buffer-seconds", type=float, default=8.0)
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    args = parse_args()
    buffer = FrameBuffer(max_frames=int(args.buffer_seconds * args.sample_fps) + args.num_frames)
    worker = CameraWorker(args.source, sample_fps=args.sample_fps)

    for frame, timestamp in worker.frames():
        buffer.append(frame, timestamp)
        window = buffer.sample_window(args.num_frames, args.sample_fps, timestamp)
        if len(window) == args.num_frames:
            print(
                f"OK smoke: captured={worker.captured_frames} buffer={len(buffer)} "
                f"window={len(window)} frame_shape={window[0].shape}"
            )
            return

    raise RuntimeError("Video terminou antes de formar uma janela amostrada.")


if __name__ == "__main__":
    main()
