from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.config import get_settings
from api.core.fall_event_crypto import decrypt_occurred_at, encrypt_occurred_at
from api.models import FallEvent


def record_fall_event(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    camera_id: uuid.UUID | None,
    occurred_at: datetime,
) -> FallEvent:
    event = FallEvent(
        workspace_id=workspace_id,
        camera_id=camera_id,
        occurred_at_encrypted=encrypt_occurred_at(
            occurred_at,
            workspace_id,
            get_settings().fall_event_encryption_keys,
        ),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_fall_events(db: Session, workspace_id: uuid.UUID) -> list[FallEvent]:
    query = select(FallEvent).where(FallEvent.workspace_id == workspace_id)
    return list(db.scalars(query).all())


def occurred_at_for_event(event: FallEvent) -> datetime:
    return decrypt_occurred_at(
        event.occurred_at_encrypted,
        event.workspace_id,
        get_settings().fall_event_encryption_keys,
    )
