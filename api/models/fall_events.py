import uuid

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    occurred_at_encrypted: Mapped[str | None] = mapped_column(Text)
    encrypted_payload: Mapped[str | None] = mapped_column(Text)
    key_envelopes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    encrypted_clip_path: Mapped[str | None] = mapped_column(Text)
    clip_key_envelopes: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


Index("idx_fall_events_workspace", FallEvent.workspace_id)
