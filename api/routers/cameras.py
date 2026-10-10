import uuid
import socket
import ssl
from datetime import UTC, datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.cache import CachePolicy, CacheScope, CachedAPIRoute, cache_response
from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, Camera
from api.schemas import CameraAutoConfigure, CameraCreate, CameraPingResponse, CameraResponse, CameraUpdate
from api.services.camera_discovery import (
    CameraConnectionNotFound,
    CameraDetectionUnavailable,
    detect_camera_connection,
)

router = APIRouter(prefix="/cameras", tags=["cameras"], route_class=CachedAPIRoute)


def _detect_connection(payload: CameraAutoConfigure):
    try:
        return detect_camera_connection(payload.host, payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except CameraConnectionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Não foi possível localizar um stream compatível nesse host.",
        ) from exc
    except CameraDetectionUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A detecção automática de câmeras não está disponível.",
        ) from exc


def _resolve_camera_ping_target(camera: Camera) -> tuple[str, int]:
    parsed = urlparse(camera.stream_url)
    scheme = (parsed.scheme or camera.connection_type or "").lower()
    metadata = camera.metadata_json or {}

    host = parsed.hostname
    if not host and isinstance(metadata.get("host"), str):
        host = metadata["host"].strip()

    if not host:
        raise ValueError("Camera host not configured")

    default_port = 554 if scheme == "rtsp" else 443 if scheme == "https" else 80
    return host, parsed.port or default_port


def _camera_has_pong(camera: Camera, timeout_seconds: float = 2.5) -> bool:
    metadata = camera.metadata_json or {}
    if metadata.get("protocol") == "local-agent-webcam":
        # The local agent updates this status after it successfully reads a frame.
        # Do not attempt a network probe for a host-side webcam (source "0").
        return camera.is_active and camera.status == "online"

    parsed = urlparse(camera.stream_url)
    scheme = (parsed.scheme or camera.connection_type or "").lower()

    if scheme in {"http", "https"}:
        return _http_camera_has_pong(camera.stream_url, timeout_seconds)

    host, port = _resolve_camera_ping_target(camera)
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _http_camera_has_pong(url: str, timeout_seconds: float) -> bool:
    request = Request(url, headers={"Accept": "text/plain, application/json, */*"})
    ssl_context = ssl._create_unverified_context() if url.lower().startswith("https://") else None

    try:
        with urlopen(request, timeout=timeout_seconds, context=ssl_context) as response:
            response.read(256)
            return 200 <= response.status < 400
    except OSError:
        return False


@router.get("", response_model=list[CameraResponse])
@cache_response(CachePolicy(key="cameras:list", tags=("cameras", "workspace_members"), scope=CacheScope.USER))
def list_cameras(
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> list[Camera]:
    require_workspace_membership(workspace_id, current_user.id, db)
    return list(db.scalars(select(Camera).where(Camera.workspace_id == workspace_id)).all())


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def create_camera(
    payload: CameraCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> Camera:
    member = require_workspace_membership(payload.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin", "caregiver"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to create camera")

    camera = Camera(
        workspace_id=payload.workspace_id,
        name=payload.name,
        external_id=payload.external_id,
        connection_type=payload.connection_type,
        stream_url=payload.stream_url,
        status=payload.status,
        is_active=payload.is_active,
        metadata_json=payload.metadata,
        created_by_user_id=current_user.id,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.post("/auto-configure", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
def auto_configure_camera(
    payload: CameraAutoConfigure,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> Camera:
    member = require_workspace_membership(payload.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin", "caregiver"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to create camera")

    detected = _detect_connection(payload)

    parsed = urlparse(detected.stream_url)
    camera_host = parsed.hostname or payload.host.strip()
    camera = Camera(
        workspace_id=payload.workspace_id,
        name=f"Câmera {camera_host}",
        connection_type=detected.connection_type,
        stream_url=detected.stream_url,
        status="online",
        is_active=True,
        metadata_json={
            "host": camera_host,
            "location": camera_host,
            "protocol": detected.protocol,
            "username": payload.username.strip(),
        },
        created_by_user_id=current_user.id,
        last_seen_at=datetime.now(UTC),
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


@router.post("/{camera_id}/auto-configure", response_model=CameraResponse)
def auto_configure_existing_camera(
    camera_id: uuid.UUID,
    payload: CameraAutoConfigure,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> Camera:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")
    if camera.workspace_id != payload.workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace does not match camera")

    member = require_workspace_membership(camera.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin", "caregiver"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to update camera")

    detected = _detect_connection(payload)
    parsed = urlparse(detected.stream_url)
    camera_host = parsed.hostname or payload.host.strip()
    metadata = dict(camera.metadata_json or {})
    metadata.update(
        {
            "host": camera_host,
            "location": camera_host,
            "protocol": detected.protocol,
            "username": payload.username.strip(),
        }
    )
    camera.name = f"Câmera {camera_host}"
    camera.connection_type = detected.connection_type
    camera.stream_url = detected.stream_url
    camera.status = "online"
    camera.is_active = True
    camera.metadata_json = metadata
    camera.last_seen_at = datetime.now(UTC)
    camera.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(camera)
    return camera


@router.get("/{camera_id}", response_model=CameraResponse)
@cache_response(CachePolicy(key="cameras:get", tags=("cameras", "workspace_members"), scope=CacheScope.USER))
def get_camera(camera_id: uuid.UUID, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)) -> Camera:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    require_workspace_membership(camera.workspace_id, current_user.id, db)
    return camera


@router.post("/{camera_id}/ping", response_model=CameraPingResponse)
def ping_camera(
    camera_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> CameraPingResponse:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    require_workspace_membership(camera.workspace_id, current_user.id, db)

    checked_at = datetime.now(UTC)
    try:
        pong = _camera_has_pong(camera)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    camera.status = "online" if pong else "offline"
    if pong:
        camera.last_seen_at = checked_at
    camera.updated_at = checked_at
    db.commit()

    return CameraPingResponse(
        camera_id=camera.id,
        pong=pong,
        status=camera.status,
        checked_at=checked_at,
    )


@router.patch("/{camera_id}", response_model=CameraResponse)
def update_camera(
    camera_id: uuid.UUID,
    payload: CameraUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> Camera:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    member = require_workspace_membership(camera.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin", "caregiver"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to update camera")

    changes = payload.model_dump(exclude_unset=True)
    if "metadata" in changes:
        changes["metadata_json"] = changes.pop("metadata")

    for field, value in changes.items():
        setattr(camera, field, value)
    camera.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(camera)
    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: uuid.UUID, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)) -> None:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    member = require_workspace_membership(camera.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete camera")

    db.delete(camera)
    db.commit()
