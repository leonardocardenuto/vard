import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser
from api.schemas import FallEventResponse
from api.services.fall_events import list_fall_events, occurred_at_for_event

router = APIRouter(prefix="/fall-events", tags=["fall-events"])


@router.get("", response_model=list[FallEventResponse])
def get_fall_events(
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(get_current_user),
) -> list[FallEventResponse]:
    require_workspace_membership(workspace_id, current_user.id, db)
    events = [
        FallEventResponse(
            id=event.id,
            workspace_id=event.workspace_id,
            camera_id=event.camera_id,
            notification_id=event.notification_id,
            occurred_at=occurred_at_for_event(event),
        )
        for event in list_fall_events(db, workspace_id)
    ]
    return sorted(events, key=lambda event: event.occurred_at, reverse=True)
