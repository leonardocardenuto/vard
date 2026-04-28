import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base
from api.models.base_mixins import CreatedAtMixin, OptionalProfileFieldsMixin, UpdatedAtMixin, UUIDPrimaryKeyMixin


class AppUser(Base, UUIDPrimaryKeyMixin, OptionalProfileFieldsMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "app_users"

    email: Mapped[str] = mapped_column(Text, nullable=False)
    credentials: Mapped["UserCredential | None"] = relationship(back_populates="user", uselist=False)


class UserCredential(Base, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "user_credentials"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[AppUser] = relationship(back_populates="credentials")
