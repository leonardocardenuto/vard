import base64
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, FallEvent
from api.schemas import FallEventClipResponse, FallEventResponse
from api.services.fall_events import list_fall_events

router = APIRouter(prefix="/fall-events", tags=["fall-events"])


@router.get("", response_model=list[FallEventResponse])
def get_fall_events(
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> list[FallEventResponse]:
    require_workspace_membership(workspace_id, current_user.id, db)
    return [
        FallEventResponse(
            id=event.id,
            workspace_id=event.workspace_id,
            camera_id=event.camera_id,
            notification_id=event.notification_id,
            encrypted_payload=event.encrypted_payload or "",
            key_envelope=event.key_envelopes.get(str(current_user.id), {}),
            has_clip=bool(event.encrypted_clip_path and event.clip_key_envelopes.get(str(current_user.id))),
        )
        for event in list_fall_events(db, workspace_id)
    ]


@router.get("/{event_id}/clip", response_model=FallEventClipResponse)
def get_fall_event_clip(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> FallEventClipResponse:
    event = db.get(FallEvent, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento não encontrado")
    require_workspace_membership(event.workspace_id, current_user.id, db)

    envelope = event.clip_key_envelopes.get(str(current_user.id), {})
    if not event.encrypted_clip_path or not envelope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trecho de vídeo indisponível")

    clips_dir = Path("var/encrypted_fall_clips").resolve()
    clip_path = Path(event.encrypted_clip_path).resolve()
    try:
        clip_path.relative_to(clips_dir)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trecho de vídeo indisponível") from exc
    if not clip_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trecho de vídeo indisponível")

    return FallEventClipResponse(
        encrypted_clip=base64.urlsafe_b64encode(clip_path.read_bytes()).decode("ascii"),
        key_envelope=envelope,
    )
