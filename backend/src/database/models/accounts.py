"""Account and session ORM models (EP02-01)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, SoftDeleteMixin, TableNameMixin, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import AuthTokenType, PlatformRole
from database.types import UTCDateTime

if TYPE_CHECKING:
    from database.models.profiles import UserProfile

auth_token_type_enum = ENUM(
    AuthTokenType,
    name="auth_token_type",
    create_type=False,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)

platform_role_enum = ENUM(
    PlatformRole,
    name="platform_role",
    create_type=False,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TableNameMixin, Base):
    """Registered account with email/password credentials."""

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    platform_role: Mapped[PlatformRole] = mapped_column(
        platform_role_enum,
        nullable=False,
        default=PlatformRole.USER,
        server_default=PlatformRole.USER.value,
    )

    sessions: Mapped[list[AuthSession]] = relationship(back_populates="user")
    auth_tokens: Mapped[list[AuthToken]] = relationship(back_populates="user")
    profile: Mapped["UserProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
    )


class AuthSession(UUIDPrimaryKeyMixin, TimestampMixin, TableNameMixin, Base):
    """Revocable bearer session token (stored hashed)."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class AuthToken(UUIDPrimaryKeyMixin, TimestampMixin, TableNameMixin, Base):
    """Single-use token for email verification or password reset."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    token_type: Mapped[AuthTokenType] = mapped_column(auth_token_type_enum, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship(back_populates="auth_tokens")
