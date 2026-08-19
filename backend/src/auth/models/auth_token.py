"""Single-use email/reset token ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import AuthTokenType
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User


class AuthToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Opaque token delivered via email for verification or password reset."""

    __tablename__ = "auth_tokens"
    __table_args__ = (
        Index("ix_auth_tokens_user_id", "user_id"),
        Index("ix_auth_tokens_token_hash", "token_hash"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_type: Mapped[AuthTokenType] = mapped_column(
        Enum(
            AuthTokenType,
            name="auth_token_type",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship(back_populates="auth_tokens")
