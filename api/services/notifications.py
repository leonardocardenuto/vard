from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from api.models import Notification
from api.services.push import enqueue_notification_push


def create_fall_detected_notification(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    camera_id: uuid.UUID | None,
    payload: dict[str, Any],
    title: str = "Queda detectada",
    body: str = "Uma possível queda foi detectada pela câmera.",
    created_by: str = "fall_monitor_worker",
) -> Notification:
    return _create_detection_notification(
        db, workspace_id=workspace_id, camera_id=camera_id, payload=payload,
        notification_type="fall_detected", title=title, body=body, created_by=created_by,
    )


def create_armed_person_detected_notification(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    camera_id: uuid.UUID | None,
    payload: dict[str, Any],
    title: str = "Possivel pessoa armada detectada",
    body: str = "Uma possivel pessoa armada foi detectada pela camera.",
    created_by: str = "armed_monitor_job",
) -> Notification:
    return _create_detection_notification(
        db, workspace_id=workspace_id, camera_id=camera_id, payload=payload,
        notification_type="armed_person_detected", title=title, body=body, created_by=created_by,
    )


def create_confrontation_detected_notification(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    camera_id: uuid.UUID | None,
    payload: dict[str, Any],
    title: str = "Possivel confronto detectado",
    body: str = "Um possivel confronto foi detectado pela camera.",
    created_by: str = "confrontation_monitor_job",
) -> Notification:
    return _create_detection_notification(
        db, workspace_id=workspace_id, camera_id=camera_id, payload=payload,
        notification_type="confrontation_detected", title=title, body=body, created_by=created_by,
    )


def _create_detection_notification(
    db: Session, *, workspace_id: uuid.UUID, camera_id: uuid.UUID | None,
    payload: dict[str, Any], notification_type: str, title: str, body: str, created_by: str,
) -> Notification:
    notification = Notification(
        workspace_id=workspace_id,
        camera_id=camera_id,
        notification_type=notification_type,
        severity="critical",
        title=title,
        body=body,
        payload=payload,
        created_by=created_by,
    )
    db.add(notification)
    db.flush()
    enqueue_notification_push(db, notification)
    db.commit()
    db.refresh(notification)
    return notification
