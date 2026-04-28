import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.db import Base
from api.models.base_mixins import CreatedAtMixin, UpdatedAtMixin, UUIDPrimaryKeyMixin


class Workspace(Base, UUIDPrimaryKeyMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'UTC'"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL"))


class WorkspaceMember(Base, CreatedAtMixin):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL"))
    joined_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member', 'caregiver', 'viewer')", name="workspace_members_role_check"),
        CheckConstraint("status IN ('active', 'pending', 'removed')", name="workspace_members_status_check"),
    )


class WorkspaceInvite(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "workspace_invites"

    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL"))
    token: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    expires_at: Mapped[datetime]
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("app_users.id", ondelete="SET NULL"))
    accepted_at: Mapped[datetime | None] = mapped_column()
    revoked_at: Mapped[datetime | None] = mapped_column()


Index("idx_workspace_members_user_id", WorkspaceMember.user_id)
Index("idx_workspace_invites_workspace_status", WorkspaceInvite.workspace_id, WorkspaceInvite.status)
