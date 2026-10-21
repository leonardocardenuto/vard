"""Persistent push outbox. Provider acceptance is not proof of device receipt."""
import hashlib
import logging
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from api.core.config import get_settings
from api.db import SessionLocal
from api.models import AppUser, Notification, PushDevice, PushDelivery, WorkspaceMember
from api.services.push_providers import PushError, send_push, close_push_transport
from api.services.push_wakeup import PushListener, notify_push

logger = logging.getLogger(__name__)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def elderly_user_ids():
    return select(WorkspaceMember.user_id).where(WorkspaceMember.role == "elderly", WorkspaceMember.status == "active")


def can_receive(db, user_id, workspace_id):
    return db.scalar(select(WorkspaceMember.user_id).where(
        WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id,
        WorkspaceMember.status == "active", WorkspaceMember.role != "elderly",
        WorkspaceMember.user_id.not_in(elderly_user_ids()))) is not None


def enqueue_delivery(db, *, user_id, provider, token, title, body, data, event_key, notification_id=None, device_id=None):
    delivery_id = uuid.uuid4()
    result = db.execute(insert(PushDelivery).values(
        id=delivery_id, user_id=user_id, provider=provider, token=token, token_hash=token_hash(token),
        title=title, body=body, data=data, event_key=event_key, notification_id=notification_id,
        device_id=device_id,
    ).on_conflict_do_nothing(constraint="push_deliveries_event_target_key").returning(PushDelivery.id)).scalar()
    if result is not None:
        notify_push(db)
    return result


def enqueue_notification_push(db, notification: Notification):
    """Call before committing the event so event + delivery persist atomically."""
    provider = get_settings().push_provider
    users = list(db.scalars(select(AppUser).join(WorkspaceMember, WorkspaceMember.user_id == AppUser.id).where(
        WorkspaceMember.workspace_id == notification.workspace_id, WorkspaceMember.status == "active",
        WorkspaceMember.role != "elderly", AppUser.id.not_in(elderly_user_ids()))).all())
    blocked_legacy = set(db.scalars(select(AppUser.onesignal_subscription_id).where(
        AppUser.id.in_(elderly_user_ids()), AppUser.onesignal_subscription_id.is_not(None))).all())
    data = {"notification_id": str(notification.id), "workspace_id": str(notification.workspace_id),
            "camera_id": str(notification.camera_id) if notification.camera_id else "",
            "notification_type": notification.notification_type, "severity": notification.severity,
            "source": notification.payload.get("source", "") if notification.payload.get("source") == "accelerometer" else "camera"}
    for user in users:
        devices = list(db.scalars(select(PushDevice).where(PushDevice.user_id == user.id,
            PushDevice.provider == provider, PushDevice.is_active.is_(True))).all())
        targets = [(device.token, device.id) for device in devices]
        if provider == "onesignal" and user.onesignal_subscription_id and not targets:
            targets = [(user.onesignal_subscription_id, None)]
        for token, device_id in targets:
            if provider == "onesignal" and token in blocked_legacy:
                continue
            enqueue_delivery(db, user_id=user.id, provider=provider, token=token, device_id=device_id,
                             title=notification.title, body=notification.body, data=data,
                             event_key=str(notification.id), notification_id=notification.id)


def process_one(db) -> bool:
    now = datetime.now(UTC)
    delivery = db.scalar(select(PushDelivery).where(PushDelivery.status == "pending",
        PushDelivery.next_attempt_at <= now).order_by(PushDelivery.created_at).with_for_update(skip_locked=True).limit(1))
    if delivery is None:
        return False
    if delivery.created_at < now - timedelta(hours=1):
        delivery.status = "expired"
        return True
    if delivery.device_id:
        device = db.get(PushDevice, delivery.device_id)
        if not device or not device.is_active or device.user_id != delivery.user_id or device.token_hash != delivery.token_hash:
            delivery.status = "cancelled"
            return True
    else:
        user = db.get(AppUser, delivery.user_id)
        if not user or delivery.provider != "onesignal" or user.onesignal_subscription_id != delivery.token:
            delivery.status = "cancelled"
            return True
    if delivery.notification_id:
        notification = db.get(Notification, delivery.notification_id)
        if not notification or not can_receive(db, delivery.user_id, notification.workspace_id):
            delivery.status = "cancelled"
            return True
    delivery.attempts += 1
    delivery.send_started_at = datetime.now(UTC)
    started = time.perf_counter()
    try:
        delivery.provider_message_id = send_push(delivery.provider, delivery.token, title=delivery.title,
            body=delivery.body, data=delivery.data, delivery_id=str(delivery.id))
        delivery.accepted_at = datetime.now(UTC)
        delivery.status = "accepted"
        delivery.last_error = None
    except PushError as error:
        delivery.last_error = str(error)
        delivery.status = "pending" if error.retryable and delivery.attempts < 8 else "failed"
        delivery.next_attempt_at = now + timedelta(seconds=min(1800, 30 * 2 ** (delivery.attempts - 1)))
        if error.invalid_token and delivery.device_id:
            device.is_active = False
    finally:
        delivery.provider_duration_ms = round((time.perf_counter() - started) * 1000)
    return True


class PushWorker:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.run, name="push-outbox", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=12)

    def run(self):
        listener = None
        try:
            while not self.stop_event.is_set():
                try:
                    if listener is None:
                        try:
                            # Subscribe before scanning to avoid a check/wait race.
                            listener = PushListener()
                        except Exception as error:
                            logger.warning("Push wake-up unavailable (%s)", type(error).__name__)
                    processed = 0
                    for _ in range(10):
                        if self.stop_event.is_set():
                            break
                        with SessionLocal.begin() as db:
                            if not process_one(db):
                                break
                        processed += 1
                    if listener is not None:
                        # Never sleep between full batches. A timeout still scans
                        # retries/recovered work even if a wake-up was lost.
                        listener.wait(0 if processed == 10 or self.stop_event.is_set() else 2)
                    elif processed < 10:
                        self.stop_event.wait(2)
                except Exception as error:
                    logger.warning("Push worker unavailable (%s)", type(error).__name__)
                    if listener is not None:
                        listener.close()
                        listener = None
                    self.stop_event.wait(2)
        finally:
            if listener is not None:
                listener.close()
            close_push_transport()
