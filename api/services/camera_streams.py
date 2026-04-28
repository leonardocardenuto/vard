import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

from api.core.config import get_settings
from api.models import Camera

settings = get_settings()
STREAMS_ROOT = Path("var/streams")
STREAMS_ROOT.mkdir(parents=True, exist_ok=True)


@dataclass
class CameraStreamProcess:
    camera_id: uuid.UUID
    source_url: str
    process: subprocess.Popen[str]


_streams_lock = Lock()
_stream_processes: dict[uuid.UUID, CameraStreamProcess] = {}


def get_stream_directory(camera_id: uuid.UUID) -> Path:
    stream_dir = STREAMS_ROOT / str(camera_id)
    stream_dir.mkdir(parents=True, exist_ok=True)
    return stream_dir


def get_stream_playlist_path(camera_id: uuid.UUID) -> Path:
    return get_stream_directory(camera_id) / "index.m3u8"


def get_stream_playlist_url(camera_id: uuid.UUID) -> str:
    return f"{settings.app_base_url.rstrip('/')}/streams/{camera_id}/index.m3u8"


def _cleanup_stream_directory(camera_id: uuid.UUID) -> None:
    stream_dir = get_stream_directory(camera_id)
    for path in stream_dir.glob("*"):
        if path.is_file():
            path.unlink()


def _build_input_options(camera: Camera) -> list[str]:
    parsed = urlparse(camera.stream_url)
    scheme = (parsed.scheme or camera.connection_type or "").lower()

    if scheme == "rtsp":
        return [
            "-rtsp_transport",
            "tcp",
            "-fflags",
            "nobuffer",
            "-flags",
            "low_delay",
        ]

    if scheme in {"http", "https"}:
        options = [
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "2",
        ]
        if scheme == "https":
            options.extend(["-tls_verify", "0"])
        return options

    return []


def _start_ffmpeg(camera: Camera) -> CameraStreamProcess:
    stream_dir = get_stream_directory(camera.id)
    playlist_path = stream_dir / "index.m3u8"
    segment_pattern = stream_dir / "segment_%03d.ts"
    log_path = stream_dir / "ffmpeg.log"

    _cleanup_stream_directory(camera.id)

    log_file = open(log_path, "w", encoding="utf-8")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        *_build_input_options(camera),
        "-i",
        camera.stream_url,
        "-an",
        "-c:v",
        "copy",
        "-f",
        "hls",
        "-hls_time",
        "2",
        "-hls_list_size",
        "6",
        "-hls_flags",
        "delete_segments+append_list+independent_segments+omit_endlist",
        "-hls_segment_filename",
        str(segment_pattern),
        str(playlist_path),
    ]
    process = subprocess.Popen(
        command,
        stdout=log_file,
        stderr=log_file,
        text=True,
    )
    return CameraStreamProcess(camera_id=camera.id, source_url=camera.stream_url, process=process)


def ensure_camera_stream(camera: Camera, timeout_seconds: float = 8.0) -> str:
    playlist_path = get_stream_playlist_path(camera.id)

    with _streams_lock:
        current = _stream_processes.get(camera.id)
        should_restart = (
            current is None
            or current.source_url != camera.stream_url
            or current.process.poll() is not None
        )

        if should_restart:
            if current and current.process.poll() is None:
                current.process.kill()
            _stream_processes[camera.id] = _start_ffmpeg(camera)

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if playlist_path.exists() and playlist_path.stat().st_size > 0:
            return get_stream_playlist_url(camera.id)

        current = _stream_processes.get(camera.id)
        if current and current.process.poll() is not None:
            break
        time.sleep(0.25)

    raise RuntimeError("Nao foi possivel iniciar o stream HLS da camera.")


def stop_camera_stream(camera_id: uuid.UUID) -> None:
    with _streams_lock:
        current = _stream_processes.pop(camera_id, None)
        if current and current.process.poll() is None:
            current.process.kill()
