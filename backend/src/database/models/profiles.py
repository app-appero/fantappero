"""User profile and preference ORM models (EP02-02)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TableNameMixin, TimestampMixin
from database.types import UTCDateTime

if TYPE_CHECKING:
    from database.models.accounts import User


class UserProfile(TableNameMixin, TimestampMixin, Base):
    """Private profile preferences linked 1:1 to an account."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, server_default="it")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="Europe/Rome")
    notifications_email: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notifications_push: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    policy_consent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")
