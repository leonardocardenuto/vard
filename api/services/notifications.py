from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models import AppUser, Notification, WorkspaceMember
from api.services.onesignal import send_push_to_subscription_ids


def create_fall_detected_notification(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    camera_id: uuid.UUID | None,
    payload: dict[str, Any],
    title: str = "Queda detectada",
    body: str = "Uma possivel queda foi detectada pela camera.",
    created_by: str = "fall_monitor_worker",
) -> Notification:
    notification = Notification(
        workspace_id=workspace_id,
        camera_id=camera_id,
        notification_type="fall_detected",
        severity="critical",
        title=title,
        body=body,
        payload=payload,
        created_by=created_by,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    subscription_ids = list(
        db.scalars(
            select(AppUser.onesignal_subscription_id)
            .join(WorkspaceMember, WorkspaceMember.user_id == AppUser.id)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
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
