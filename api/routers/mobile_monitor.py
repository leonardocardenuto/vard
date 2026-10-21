import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from api.db import get_db
from api.deps import get_current_user, require_workspace_membership
from api.models import AppUser, MobileMonitorDevice, Notification, Workspace, WorkspaceMember
from api.services.push import enqueue_notification_push

router = APIRouter(prefix="/mobile-monitor", tags=["mobile-monitor"])


class Registration(BaseModel):
    workspace_id: uuid.UUID


class MobileFall(BaseModel):
    event_id: uuid.UUID
    occurred_at: datetime
    peak_g: float = Field(ge=0, le=100)


@router.get("/profile")
def profile(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    rows = db.execute(
        select(WorkspaceMember, Workspace).join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == user.id, WorkspaceMember.status == "active")
    ).all()
    return {
        "restricted": any(member.role == "elderly" for member, _ in rows),
        "workspaces": [{"id": str(ws.id), "name": ws.name} for member, ws in rows if member.role == "elderly"],
    }


@router.post("/devices")
def register(payload: Registration, db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    member = require_workspace_membership(payload.workspace_id, user.id, db, allow_elderly=True)
    if member.role != "elderly":
        raise HTTPException(403, "O monitoramento pessoal exige um convite com perfil Idoso.")
    token = secrets.token_urlsafe(48)
    device = MobileMonitorDevice(user_id=user.id, workspace_id=payload.workspace_id,
                                 token_hash=hashlib.sha256(token.encode()).hexdigest())
    db.add(device)
    db.commit()
    return {"device_id": str(device.id), "device_token": token}


def current_device(authorization: str = Header(...), db: Session = Depends(get_db)):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Credencial de monitoramento inválida.")
    device = db.scalar(select(MobileMonitorDevice).where(
        MobileMonitorDevice.token_hash == hashlib.sha256(token.encode()).hexdigest(),
        MobileMonitorDevice.revoked_at.is_(None),
    ))
    if not device:
        raise HTTPException(401, "Monitoramento revogado. Entre novamente.")
    member = require_workspace_membership(device.workspace_id, device.user_id, db, allow_elderly=True)
    if member.role != "elderly":
        raise HTTPException(403, "Perfil Idoso não está mais ativo neste espaço.")
    return device


@router.get("/devices/current")
def heartbeat(db: Session = Depends(get_db), device: MobileMonitorDevice = Depends(current_device)):
    device.last_seen_at = datetime.now(UTC)
    db.commit()
    return {"active": True, "workspace_id": str(device.workspace_id)}


@router.delete("/devices/current", status_code=204)
def revoke_current(db: Session = Depends(get_db), device: MobileMonitorDevice = Depends(current_device)):
    device.revoked_at = datetime.now(UTC)
    db.commit()


@router.delete("/devices", status_code=204)
def revoke_all(db: Session = Depends(get_db), user: AppUser = Depends(get_current_user)):
    db.execute(update(MobileMonitorDevice).where(MobileMonitorDevice.user_id == user.id)
               .values(revoked_at=datetime.now(UTC)))
    db.commit()


@router.post("/falls")
def report_fall(payload: MobileFall, tasks: BackgroundTasks, db: Session = Depends(get_db),
                device: MobileMonitorDevice = Depends(current_device)):
    if payload.occurred_at.tzinfo is None or payload.occurred_at > datetime.now(UTC) + timedelta(minutes=5):
        raise HTTPException(422, "Horário da ocorrência inválido.")
    # Serialize reports per device; UUID idempotency prevents offline retries
    # from generating another notification or push.
    db.refresh(device, with_for_update=True)
    if device.revoked_at is not None:
        raise HTTPException(401, "Monitoramento revogado. Entre novamente.")
    existing = db.get(Notification, payload.event_id)
    if existing:
        if existing.payload.get("device_id") != str(device.id):
            raise HTTPException(409, "Identificador de ocorrência já utilizado.")
        return {"notification_id": str(existing.id)}
    user = db.get(AppUser, device.user_id)
    title = "Possível queda detectada pelo celular"
    body = f"{user.full_name or user.email} não cancelou o alerta de possível queda. Verifique se precisa de ajuda."
    values = dict(id=payload.event_id, workspace_id=device.workspace_id, camera_id=None,
                  notification_type="fall_detected", severity="critical", title=title, body=body,
                  created_by="mobile_fall_monitor", payload={
                      "source": "accelerometer", "location": "Celular", "device_id": str(device.id),
                      "user_id": str(device.user_id), "occurred_at": payload.occurred_at.isoformat(),
                      "peak_g": payload.peak_g, "confirmation": "timeout",
                  })
    inserted = db.execute(insert(Notification).values(**values).on_conflict_do_nothing(
        index_elements=[Notification.id]).returning(Notification.id)).scalar()
    if inserted is None:
        raise HTTPException(409, "Identificador de ocorrência já utilizado.")
    device.last_seen_at = datetime.now(UTC)
    enqueue_notification_push(db, db.get(Notification, payload.event_id))
    db.info.setdefault("cache_invalidation_tags", set()).add("notifications")
    db.commit()
    return {"notification_id": str(payload.event_id)}
