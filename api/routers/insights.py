import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, Camera, Notification

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/summary")
def get_insights_summary(
    workspace_id: uuid.UUID = Query(...),
    days: int = Query(default=90, ge=1, le=365),
    camera_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> dict[str, Any]:
    require_workspace_membership(workspace_id, current_user.id, db)

    now = datetime.now(UTC)
    start_at = now - timedelta(days=days)

    cameras = {
        camera.id: camera
        for camera in db.scalars(
            select(Camera).where(Camera.workspace_id == workspace_id)
        ).all()
    }
    notifications = list(
        db.scalars(
            select(Notification)
            .where(
                Notification.workspace_id == workspace_id,
                Notification.created_at >= start_at,
            )
            .order_by(Notification.created_at.desc())
        ).all()
    )

    if camera_id is not None:
        notifications = [
            notification
            for notification in notifications
            if notification.camera_id == camera_id
        ]

    current_falls = [
        notification
        for notification in notifications
        if (
            _is_fall_notification(notification)
            and notification.created_at >= start_at
        )
    ]
    countable_falls = [
        notification
        for notification in current_falls
        if _incident_status(notification.payload) != "false_positive"
    ]

    return {
        "workspace_id": str(workspace_id),
        "camera_id": str(camera_id) if camera_id else None,
        "period_days": days,
        "total_falls": len(countable_falls),
        "false_positives": len(current_falls) - len(countable_falls),
        "by_room": _counts_by_room(countable_falls, cameras),
        "by_day": _counts_by_day(countable_falls),
    }


def _is_fall_notification(notification: Notification) -> bool:
    searchable_text = f"{notification.notification_type} {notification.title}".lower()
    return "fall" in searchable_text or "queda" in searchable_text


def _incident_status(payload: dict[str, Any]) -> str:
    resolution = payload.get("incident_resolution")
    if isinstance(resolution, dict):
        status = resolution.get("status")
        if status in {"confirmed", "false_positive", "resolved"}:
            return str(status)

    validation = payload.get("detection_validation")
    if isinstance(validation, dict):
        is_valid = validation.get("is_valid")
        if is_valid is False:
            return "false_positive"
        if is_valid is True:
            return "confirmed"

    return "new"


def _counts_by_room(
    notifications: list[Notification],
    cameras: dict[uuid.UUID, Camera],
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for notification in notifications:
        camera = cameras.get(notification.camera_id) if notification.camera_id else None
        room = _notification_room(notification, camera)
        counts[room] = counts.get(room, 0) + 1

    return [
        {"room": room, "value": value}
        for room, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def _counts_by_day(notifications: list[Notification]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for notification in notifications:
        key = notification.created_at.date().isoformat()
        counts[key] = counts.get(key, 0) + 1

    return [
        {"date": date, "value": value}
        for date, value in sorted(counts.items())
    ]


def _notification_room(notification: Notification, camera: Camera | None) -> str:
    payload_room = notification.payload.get("room")
    if isinstance(payload_room, str) and payload_room.strip():
        return payload_room.strip()

    metadata = camera.metadata_json if camera else {}
    metadata_room = metadata.get("room")
    if isinstance(metadata_room, str) and metadata_room.strip():
        return metadata_room.strip()

    return camera.name if camera else notification.notification_type
