import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base
from api.models.base_mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class PushDevice(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "push_devices"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), index=True)
    installation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(Text)
    token: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    __table_args__ = (
        UniqueConstraint("installation_id", "provider", name="push_devices_installation_provider_key"),
        UniqueConstraint("provider", "token_hash", name="push_devices_provider_token_key"),
    )


class PushDelivery(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "push_deliveries"
    notification_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("push_devices.id", ondelete="SET NULL"))
    event_key: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    token: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(Text, default="pending", server_default=text("'pending'"), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    send_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_duration_ms: Mapped[int | None] = mapped_column(Integer)
    receipt_source: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("event_key", "provider", "token_hash", name="push_deliveries_event_target_key"),)
