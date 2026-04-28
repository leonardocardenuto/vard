import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, Notification
from api.schemas import NotificationCreate, NotificationResponse, NotificationUpdate

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
def list_notifications(
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> list[Notification]:
    require_workspace_membership(workspace_id, current_user.id, db)
    query = (
        select(Notification)
        .where(Notification.workspace_id == workspace_id)
        .order_by(Notification.created_at.desc())
    )
    return list(db.scalars(query).all())


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> Notification:
    member = require_workspace_membership(payload.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin", "caregiver"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to create notifications")

    notification = Notification(**payload.model_dump())
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> Notification:
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    require_workspace_membership(notification.workspace_id, current_user.id, db)
    return notification


@router.patch("/{notification_id}", response_model=NotificationResponse)
def update_notification(
    notification_id: uuid.UUID,
    payload: NotificationUpdate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> Notification:
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    member = require_workspace_membership(notification.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin", "caregiver"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to update notifications")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(notification, field, value)

    db.commit()
    db.refresh(notification)
    return notification


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> None:
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    member = require_workspace_membership(notification.workspace_id, current_user.id, db)
    if member.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete notifications")

    db.delete(notification)
    db.commit()
