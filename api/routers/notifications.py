import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.cache import CachePolicy, CacheScope, CachedAPIRoute, cache_response
from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, Notification, WorkspaceMember
from api.schemas import NotificationCreate, NotificationResponse, NotificationUpdate
from api.services.onesignal import send_push_to_subscription_ids

router = APIRouter(prefix="/notifications", tags=["notifications"], route_class=CachedAPIRoute)


@router.get("", response_model=list[NotificationResponse])
@cache_response(CachePolicy(key="notifications:list", tags=("notifications", "workspace_members"), scope=CacheScope.USER))
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

    subscription_ids = list(
        db.scalars(
            select(AppUser.onesignal_subscription_id)
            .join(WorkspaceMember, WorkspaceMember.user_id == AppUser.id)
            .where(
                WorkspaceMember.workspace_id == notification.workspace_id,
                WorkspaceMember.status == "active",
                AppUser.onesignal_subscription_id.is_not(None),
            )
        ).all()
    )
    send_push_to_subscription_ids(
        subscription_ids,
        title=notification.title,
        body=notification.body,
        data={
            "notification_id": str(notification.id),
            "workspace_id": str(notification.workspace_id),
            "camera_id": str(notification.camera_id) if notification.camera_id else None,
            "notification_type": notification.notification_type,
            "severity": notification.severity,
        },
    )
    return notification


@router.get("/{notification_id}", response_model=NotificationResponse)
@cache_response(CachePolicy(key="notifications:get", tags=("notifications", "workspace_members"), scope=CacheScope.USER))
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
