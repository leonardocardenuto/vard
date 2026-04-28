import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base
from api.models.base_mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class NotificationChannel(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "notification_channels"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False)
    channel_type: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class Notification(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "notifications"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    camera_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="SET NULL"))
    notification_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'high'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'system'"))


class NotificationDelivery(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "notification_deliveries"

    notification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False)
    channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))
    error_message: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column()
    read_at: Mapped[datetime | None] = mapped_column()


Index("idx_notification_channels_user", NotificationChannel.user_id)
Index("idx_notifications_workspace_created_at", Notification.workspace_id, Notification.created_at.desc())
Index("idx_notifications_camera_created_at", Notification.camera_id, Notification.created_at.desc())
Index("idx_notification_deliveries_status_created_at", NotificationDelivery.status, NotificationDelivery.created_at.desc())
