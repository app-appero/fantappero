"""User account ORM model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import PlatformRole, UserType
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.auth_session import AuthSession
    from auth.models.auth_token import AuthToken
    from auth.models.user_profile import UserProfile
    from leagues.models.league_membership import LeagueMembership


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Registered platform user with email/password credentials."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    platform_role: Mapped[PlatformRole] = mapped_column(
        Enum(
            PlatformRole,
            name="platform_role",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    user_type: Mapped[UserType] = mapped_column(
        Enum(
            UserType,
            name="user_type",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=UserType.HUMAN,
        server_default=text("'human'"),
    )

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    auth_tokens: Mapped[list[AuthToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    profile: Mapped[UserProfile | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    league_memberships: Mapped[list[LeagueMembership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def display_name(self) -> str:
        if self.profile is not None and self.profile.display_name:
            return self.profile.display_name
        local_part = self.email.split("@", maxsplit=1)[0]
        return local_part or self.email
