from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import cv2


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = REPO_ROOT / "var" / "best_vjepa2_fall_classifier_combined.pt"


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Valida uma camera RTSP configurada por ambiente e roda o detector. "
            "Foi feito para um no local conectado ao Tailscale, sem port-forward no roteador."
        )
    )
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--source-env", default="VARD_RTSP_URL")
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    parser.add_argument("--device", default="mps")
    parser.add_argument("--sample-fps", type=float, default=6.0)
    parser.add_argument("--window-seconds", type=float, default=None)
    parser.add_argument("--stride-seconds", type=float, default=1.0)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--no-tailscale-check", action="store_true")
    parser.add_argument("--rtsp-open-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--max-inferences", type=int, default=0)
    parser.add_argument("--show-preview", action="store_true")
    return parser.parse_args()


def load_dotenv(path: Path):
    if not path.exists():
        return
    with path.open(encoding="utf-8") as env_file:
        for line in env_file:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def mask_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.scheme or "@" not in parts.netloc:
        return value
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port is not None else ""
    return urlunsplit((parts.scheme, f"***:***@{host}{port}", parts.path, parts.query, parts.fragment))


def require_rtsp_url(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise RuntimeError(f"Defina {env_name} no ambiente ou no .env.")
    scheme = urlsplit(value).scheme.lower()
    if scheme not in {"rtsp", "rtsps"}:
        raise RuntimeError(f"{env_name} precisa ser rtsp:// ou rtsps://.")
    return value


def run_command(command: list[str], timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def check_tailscale():
    if not shutil.which("tailscale"):
        print("tailscale CLI nao encontrado. Instale/abra o Tailscale nesse host local.")
        return False

    status = run_command(["tailscale", "status", "--peers=false"])
    if status.returncode != 0:
        print("tailscale status falhou. Rode `tailscale up` neste host local.")
        print(status.stderr.strip() or status.stdout.strip())
        return False

    ip = run_command(["tailscale", "ip", "-4"])
    tailscale_ip = ip.stdout.strip().splitlines()[0] if ip.returncode == 0 and ip.stdout.strip() else "desconhecido"
    print(f"Tailscale ativo neste host. IP Tailscale: {tailscale_ip}")
    return True


def check_rtsp_opens(url: str, timeout_seconds: float) -> bool:
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    deadline = time.monotonic() + timeout_seconds
    ok = False
    while time.monotonic() < deadline:
        ok, _frame = cap.read()
        if ok:
            break
        time.sleep(0.2)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    if ok:
        print(f"RTSP abriu com sucesso: {width}x{height} fps={fps:.2f}")
        return True
    print("Nao consegui ler frame do RTSP dentro do timeout.")
    return False


def run_detector(args, source_env: str):
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_fall_detection.py"),
        "--mode",
        "stream",
        "--source",
        f"env:{source_env}",
        "--checkpoint",
        args.checkpoint,
        "--device",
        args.device,
        "--sample-fps",
        str(args.sample_fps),
        "--stride-seconds",
        str(args.stride_seconds),
    ]
    if args.window_seconds is not None:
        command.extend(["--window-seconds", str(args.window_seconds)])
    if args.max_inferences:
        command.extend(["--max-inferences", str(args.max_inferences)])
    if args.show_preview:
        command.append("--show-preview")
    print("Subindo detector RTSP via env. Credenciais nao serao impressas.")
    return subprocess.call(command, cwd=str(REPO_ROOT))


def main():
    args = parse_args()
    load_dotenv(Path(args.env_file))
    url = require_rtsp_url(args.source_env)
    print(f"RTSP source: {mask_url(url)}")

    tailscale_ok = True
    if not args.no_tailscale_check:
        tailscale_ok = check_tailscale()

    rtsp_ok = check_rtsp_opens(url, args.rtsp_open_timeout_seconds)
    if args.check_only:
        return 0 if tailscale_ok and rtsp_ok else 1
    if not rtsp_ok:
        return 1
    return run_detector(args, args.source_env)


if __name__ == "__main__":
    raise SystemExit(main())
