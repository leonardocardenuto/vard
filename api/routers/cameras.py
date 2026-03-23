import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, Camera
from api.schemas import CameraCreate, CameraResponse, CameraUpdate

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("", response_model=list[CameraResponse])
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


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(camera_id: uuid.UUID, db: Session = Depends(get_db), current_user: AppUser = Depends(get_current_user)) -> Camera:
    camera = db.get(Camera, camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    require_workspace_membership(camera.workspace_id, current_user.id, db)
    return camera


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
