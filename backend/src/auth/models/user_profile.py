"""User profile ORM model (display name and preferences)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User


class UserProfile(Base, TimestampMixin):
    """Extended profile data keyed by user account."""

    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(
            "quiet_hours_start_hour IS NULL OR quiet_hours_start_hour BETWEEN 0 AND 23",
            name="ck_user_profiles_quiet_hours_start_hour",
        ),
        CheckConstraint(
            "quiet_hours_end_hour IS NULL OR quiet_hours_end_hour BETWEEN 0 AND 23",
            name="ck_user_profiles_quiet_hours_end_hour",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'it'"))
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'Europe/Rome'"),
    )
    notifications_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    notifications_push: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    # Local hour (0-23, in ``timezone`` above) during which external channel
    # notifications (email/push) are deferred (EP09-05). Both null = no quiet
    # hours configured. Never affects the in-app center, which is always live.
    quiet_hours_start_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quiet_hours_end_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_for_invites: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    policy_consent_at: Mapped[object | None] = mapped_column(UTCDateTime(), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")
