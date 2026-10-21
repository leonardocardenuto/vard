import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update, or_

from api.db import get_db
from api.deps import get_current_user
from api.models import AppUser, PushDevice, PushDelivery
from api.services.push import enqueue_delivery, token_hash

router = APIRouter(prefix="/push", tags=["push"])


class DeviceRegistration(BaseModel):
    installation_id: uuid.UUID
    provider: Literal["fcm", "onesignal"]
    token: str = Field(min_length=8, max_length=4096)


class TestPush(BaseModel):
    provider: Literal["fcm", "onesignal"]
    installation_id: uuid.UUID
    benchmark: bool = False


class PushReceipt(BaseModel):
    source: Literal["foreground", "tap"]


def elapsed_ms(start, end):
    return round((end - start).total_seconds() * 1000) if start and end else None


@router.post("/devices")
def register_device(payload: DeviceRegistration, db=Depends(get_db), user: AppUser = Depends(get_current_user)):
    # A token belongs to one account/installation at a time, including after logout/login.
    hashed = token_hash(payload.token)
    matches = list(db.scalars(select(PushDevice).where(PushDevice.provider == payload.provider,
        or_(PushDevice.installation_id == payload.installation_id, PushDevice.token_hash == hashed))
        .with_for_update()).all())
    device = next((item for item in matches if item.token_hash == hashed), None)
    if device is None:
        device = next(iter(matches), None)
    for old in matches:
        if old is not device:
            db.execute(update(PushDelivery).where(PushDelivery.device_id == old.id,
                PushDelivery.status == "pending").values(status="cancelled"))
            db.delete(old)
    db.flush()
    if device is None:
        device = PushDevice(provider=payload.provider)
        db.add(device)
    device.user_id = user.id
    device.installation_id = payload.installation_id
    device.token = payload.token
    device.token_hash = hashed
    device.is_active = True
    if payload.provider == "onesignal":
        db.execute(update(AppUser).where(AppUser.id != user.id,
            AppUser.onesignal_subscription_id == payload.token).values(onesignal_subscription_id=None))
        user.onesignal_subscription_id = payload.token
    db.commit()
    db.refresh(device)
    return {"id": str(device.id), "provider": device.provider}


@router.delete("/devices/{installation_id}", status_code=204)
def revoke_devices(installation_id: uuid.UUID, db=Depends(get_db), user: AppUser = Depends(get_current_user)):
    db.execute(update(PushDevice).where(PushDevice.user_id == user.id,
        PushDevice.installation_id == installation_id).values(is_active=False))
    db.commit()


@router.post("/test", status_code=202)
def test_push(payload: TestPush, db=Depends(get_db), user: AppUser = Depends(get_current_user)):
    # Serialize concurrent tests for this account before checking the limit.
    db.execute(select(AppUser.id).where(AppUser.id == user.id).with_for_update())
    count = db.scalar(select(func.count()).select_from(PushDelivery).where(PushDelivery.user_id == user.id,
        PushDelivery.notification_id.is_(None), PushDelivery.created_at > datetime.now(UTC) - timedelta(minutes=1)))
    if count >= 5:
        raise HTTPException(429, "Aguarde um minuto antes de enviar outro teste.")
    device = db.scalar(select(PushDevice).where(PushDevice.user_id == user.id,
        PushDevice.installation_id == payload.installation_id, PushDevice.provider == payload.provider,
        PushDevice.is_active.is_(True)))
    if device is None:
        raise HTTPException(409, "Este aparelho ainda não está registrado nesse provedor.")
    label = "FCM direto · sem OneSignal" if payload.provider == "fcm" else "OneSignal"
    delivery_id = enqueue_delivery(db, user_id=user.id, device_id=device.id, provider=payload.provider,
        token=device.token, title="VARD · Teste de latência" if payload.benchmark else f"VARD · Teste {label}",
        body="Notificação de teste. Nenhuma ocorrência foi criada.",
        data={"notification_type": "push_test"}, event_key=f"test:{uuid.uuid4()}")
    db.commit()
    return {"delivery_id": str(delivery_id), "provider": payload.provider, "status": "pending"}


@router.get("/deliveries/{delivery_id}")
def delivery_status(delivery_id: uuid.UUID, db=Depends(get_db), user: AppUser = Depends(get_current_user)):
    delivery = db.get(PushDelivery, delivery_id)
    if not delivery or delivery.user_id != user.id:
        raise HTTPException(404, "Envio não encontrado.")
    return {"id": str(delivery.id), "provider": delivery.provider, "status": delivery.status,
            "created_at": delivery.created_at, "send_started_at": delivery.send_started_at,
            "attempts": delivery.attempts, "accepted_at": delivery.accepted_at,
            "received_at": delivery.received_at, "receipt_source": delivery.receipt_source,
            "timing_ms": {
                "queue": elapsed_ms(delivery.created_at, delivery.send_started_at),
                "provider_request": delivery.provider_duration_ms,
                "confirmation": elapsed_ms(delivery.created_at, delivery.received_at),
                "send_to_confirmation": elapsed_ms(delivery.send_started_at, delivery.received_at),
            }, "error": delivery.last_error}


@router.post("/deliveries/{delivery_id}/received", status_code=204)
def acknowledge(delivery_id: uuid.UUID, payload: PushReceipt | None = None,
                db=Depends(get_db), user: AppUser = Depends(get_current_user)):
    delivery = db.scalar(select(PushDelivery).where(PushDelivery.id == delivery_id,
        PushDelivery.user_id == user.id).with_for_update())
    if not delivery:
        raise HTTPException(404, "Envio não encontrado.")
    if delivery.received_at is None:
        delivery.received_at = datetime.now(UTC)
        delivery.receipt_source = payload.source if payload else "unknown"
        delivery.status = "received"
        db.commit()
