import uuid
import time
import secrets
import threading
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, Camera
from api.services.camera_streams import ensure_camera_stream, get_stream_playlist_url, stop_camera_stream

router = APIRouter(prefix="/camera-streams", tags=["camera-streams"])
_preview_tickets: dict[str, tuple[uuid.UUID, float]] = {}
_preview_tickets_lock = threading.Lock()


def _create_preview_ticket(camera_id: uuid.UUID) -> str:
    ticket = secrets.token_urlsafe(24)
    now = time.monotonic()
    with _preview_tickets_lock:
        expired = [value for value, (_, expires_at) in _preview_tickets.items() if expires_at <= now]
        for value in expired:
            _preview_tickets.pop(value, None)
        _preview_tickets[ticket] = (camera_id, now + 28_800)
    return ticket


def _has_valid_preview_ticket(camera_id: uuid.UUID, ticket: str) -> bool:
    with _preview_tickets_lock:
        record = _preview_tickets.get(ticket)
    return record is not None and record[0] == camera_id and record[1] > time.monotonic()


def _mjpeg_frames(supervisor, camera_id: uuid.UUID):
    while True:
        image = supervisor.snapshot_jpeg(camera_id)
        if image is not None:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                + f"Content-Length: {len(image)}\r\n\r\n".encode()
                + image
                + b"\r\n"
            )
        time.sleep(0.125)


@router.get("/{camera_id}/snapshot")
def get_camera_snapshot(
    camera_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> Response:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    require_workspace_membership(camera.workspace_id, current_user.id, db)

    supervisor = getattr(request.app.state, "fall_monitor_supervisor", None)
    image = supervisor.snapshot_jpeg(camera_id) if supervisor else None
    if image is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Camera preview is not ready")

    return Response(content=image, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/{camera_id}/mjpeg")
def stream_camera_mjpeg(
    camera_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> StreamingResponse:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    require_workspace_membership(camera.workspace_id, current_user.id, db)

    supervisor = getattr(request.app.state, "fall_monitor_supervisor", None)
    if supervisor is None or supervisor.snapshot_jpeg(camera_id) is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Camera preview is not ready")

    return StreamingResponse(
        _mjpeg_frames(supervisor, camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.get("/{camera_id}/live")
def get_camera_live_page(
    camera_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> HTMLResponse:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    require_workspace_membership(camera.workspace_id, current_user.id, db)
    ticket = _create_preview_ticket(camera_id)
    return HTMLResponse(
        "<!doctype html><html><head><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<style>html,body,img{margin:0;width:100%;height:100%;background:#000;object-fit:contain;overflow:hidden}</style>"
        "</head><body><img id=\"camera\" src=\"/camera-streams/"
        f"{camera_id}/mjpeg/{ticket}\" alt=\"Câmera ao vivo\">"
        "<script>const camera=document.getElementById('camera');const source=camera.src;"
        "camera.onerror=()=>setTimeout(()=>camera.src=source+'?reconnect='+Date.now(),1500);</script>"
        "</body></html>",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{camera_id}/mjpeg/{ticket}", include_in_schema=False)
def stream_camera_mjpeg_with_ticket(camera_id: uuid.UUID, ticket: str, request: Request) -> StreamingResponse:
    if not _has_valid_preview_ticket(camera_id, ticket):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Camera preview access expired")
    supervisor = getattr(request.app.state, "fall_monitor_supervisor", None)
    if supervisor is None or supervisor.snapshot_jpeg(camera_id) is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Camera preview is not ready")
    return StreamingResponse(
        _mjpeg_frames(supervisor, camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@router.post("/{camera_id}/hls")
def start_camera_hls_stream(
    camera_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> dict[str, str]:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    require_workspace_membership(camera.workspace_id, current_user.id, db)

    try:
        playlist_url = ensure_camera_stream(camera)
    except RuntimeError as exc:
        camera.status = "error"
        camera.updated_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    camera.status = "online"
    camera.last_seen_at = datetime.now(UTC)
    camera.updated_at = datetime.now(UTC)
    db.commit()

    return {"playlist_url": playlist_url, "stream_type": "hls"}


@router.delete("/{camera_id}/hls", status_code=status.HTTP_204_NO_CONTENT)
def stop_camera_hls_stream(
    camera_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> None:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    require_workspace_membership(camera.workspace_id, current_user.id, db)
    stop_camera_stream(camera_id)
    camera.status = "offline"
    camera.updated_at = datetime.now(UTC)
    db.commit()
