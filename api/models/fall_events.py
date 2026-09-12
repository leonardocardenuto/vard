import uuid

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base
from api.models.base_mixins import UUIDPrimaryKeyMixin


class FallEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "fall_events"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    camera_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cameras.id", ondelete="SET NULL")
    )
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="SET NULL"), unique=True
    )
    occurred_at_encrypted: Mapped[str] = mapped_column(Text, nullable=False)


Index("idx_fall_events_workspace", FallEvent.workspace_id)
