import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, Camera
from api.services.camera_streams import ensure_camera_stream, get_stream_playlist_url, stop_camera_stream

router = APIRouter(prefix="/camera-streams", tags=["camera-streams"])


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
