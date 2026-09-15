from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.core.e2ee import encrypt_bytes_for_recipients, encrypt_for_recipients
from api.models import AppUser, FallEvent, WorkspaceMember


def record_fall_event(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    camera_id: uuid.UUID | None,
    occurred_at: datetime,
    clip_bytes: bytes | None = None,
) -> FallEvent:
    recipients = dict(db.execute(select(WorkspaceMember.user_id, AppUser.encryption_public_key).join(AppUser, AppUser.id == WorkspaceMember.user_id).where(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.status == "active", AppUser.encryption_public_key.is_not(None))).all())
    encrypted_payload, key_envelopes = encrypt_for_recipients(occurred_at, recipients)
    encrypted_clip_path = None
    clip_key_envelopes = {}
    if clip_bytes:
        encrypted_clip, clip_key_envelopes = encrypt_bytes_for_recipients(clip_bytes, recipients)
        clip_dir = Path("var/encrypted_fall_clips")
        clip_dir.mkdir(parents=True, exist_ok=True)
        clip_path = clip_dir / f"{uuid.uuid4().hex}.enc"
        clip_path.write_bytes(encrypted_clip)
        encrypted_clip_path = str(clip_path)
    event = FallEvent(
        workspace_id=workspace_id,
        camera_id=camera_id,
        encrypted_payload=encrypted_payload,
        key_envelopes=key_envelopes,
        encrypted_clip_path=encrypted_clip_path,
        clip_key_envelopes=clip_key_envelopes,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_fall_events(db: Session, workspace_id: uuid.UUID) -> list[FallEvent]:
    query = select(FallEvent).where(FallEvent.workspace_id == workspace_id)
    return list(db.scalars(query).all())
