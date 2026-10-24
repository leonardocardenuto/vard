import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base
from api.models.base_mixins import UUIDPrimaryKeyMixin, CreatedAtMixin


class MobileMonitorDevice(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "mobile_monitor_devices"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MobileMonitorSettings(Base):
    __tablename__ = "mobile_monitor_settings"
    __table_args__ = (CheckConstraint("id = 1", name="mobile_monitor_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
