from __future__ import annotations

import socket
import subprocess
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit


RTSP_PATHS = (
    "/cam/realmonitor?channel=1&subtype=0",
    "/Streaming/Channels/101",
    "/live/ch00_0",
    "/stream1",
    "/live",
    "/",
)
HTTP_PATHS = ("/video", "/video_feed", "/mjpeg", "/stream", "/")


class CameraConnectionNotFound(Exception):
    pass


class CameraDetectionUnavailable(Exception):
    pass


@dataclass(frozen=True)
class DetectedCameraConnection:
    connection_type: str
    protocol: str
    stream_url: str


def detect_camera_connection(host: str, username: str, password: str) -> DetectedCameraConnection:
    normalized_host = host.strip()
    normalized_username = username.strip()

    if not normalized_host or not normalized_username or not password:
        raise ValueError("Host, username and password are required")

    parsed_input = urlsplit(
        normalized_host if "://" in normalized_host else f"//{normalized_host}"
    )
    hostname = parsed_input.hostname
    if not hostname:
        raise ValueError("Invalid camera host")

    candidates = _build_candidates(parsed_input, normalized_username, password)
    open_targets: dict[tuple[str, int], bool] = {}

    for stream_url in candidates:
        parsed = urlsplit(stream_url)
        port = parsed.port or (554 if parsed.scheme == "rtsp" else 443 if parsed.scheme == "https" else 80)
        target = (parsed.hostname or hostname, port)

        if target not in open_targets:
            open_targets[target] = _port_is_open(*target)
        if not open_targets[target]:
            continue

        if _ffprobe_has_video(stream_url):
            is_rtsp = parsed.scheme == "rtsp"
            return DetectedCameraConnection(
                connection_type="rtsp" if is_rtsp else "https",
                protocol="rtsp-auto" if is_rtsp else "http-auto",
                stream_url=stream_url,
            )

    raise CameraConnectionNotFound("No compatible camera stream was found")


def _build_candidates(parsed_input, username: str, password: str) -> list[str]:
    hostname = parsed_input.hostname or ""
    explicit_port = parsed_input.port
    candidates: list[str] = []

    if parsed_input.scheme in {"rtsp", "http", "https"}:
        candidates.append(_url_with_credentials(parsed_input, username, password))

    rtsp_ports = _unique([explicit_port, 554, 8554])
    http_targets = _unique(
        [
            (parsed_input.scheme, explicit_port)
            if parsed_input.scheme in {"http", "https"} and explicit_port
            else None,
            ("http", 80),
            ("https", 443),
            ("http", 8080),
        ]
    )

    for port in rtsp_ports:
        for path in RTSP_PATHS:
            candidates.append(_build_url("rtsp", hostname, port, path, username, password))

    for scheme, port in http_targets:
        for path in HTTP_PATHS:
            candidates.append(_build_url(scheme, hostname, port, path, username, password))

    return list(dict.fromkeys(candidates))


def _build_url(scheme: str, host: str, port: int, path: str, username: str, password: str) -> str:
    escaped_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    credentials = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    default_port = 554 if scheme == "rtsp" else 443 if scheme == "https" else 80
    port_suffix = "" if port == default_port else f":{port}"
    return f"{scheme}://{credentials}{escaped_host}{port_suffix}{path}"


def _url_with_credentials(parsed, username: str, password: str) -> str:
    host = parsed.hostname or ""
    escaped_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    credentials = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    port_suffix = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    return urlunsplit((parsed.scheme, f"{credentials}{escaped_host}{port_suffix}", path, parsed.query, ""))


def _port_is_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return True
    except OSError:
        return False


def _ffprobe_has_video(stream_url: str) -> bool:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-rw_timeout",
        "4000000",
    ]
    if stream_url.startswith("rtsp://"):
        command.extend(["-rtsp_transport", "tcp"])
    command.extend(
        [
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            stream_url,
        ]
    )

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except FileNotFoundError:
        return _opencv_has_video(stream_url)
    except subprocess.TimeoutExpired:
        return False

    if result.returncode in {-6, 134} or "Library not loaded" in result.stderr:
        return _opencv_has_video(stream_url)

    return result.returncode == 0 and "video" in result.stdout.lower()


def _opencv_has_video(stream_url: str) -> bool:
    try:
        import cv2
    except ImportError as exc:
        raise CameraDetectionUnavailable("Neither ffprobe nor OpenCV is available") from exc

    capture = cv2.VideoCapture(
        stream_url,
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            4_000,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            4_000,
        ],
    )
    try:
        opened, frame = capture.read()
        return bool(opened and frame is not None and frame.size > 0)
    finally:
        capture.release()


def _unique(values):
    return list(dict.fromkeys(value for value in values if value is not None))
