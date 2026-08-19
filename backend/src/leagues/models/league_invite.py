"""Revocable, expiring invitation to join a private league."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User
    from leagues.models.league import League


class LeagueInvite(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Multi-use invite whose secrets are persisted only as hashes."""

    __tablename__ = "league_invites"
    __table_args__ = (
        Index("ix_league_invites_league_id", "league_id"),
        Index("ix_league_invites_token_hash", "token_hash", unique=True),
        Index("ix_league_invites_code_hash", "code_hash", unique=True),
        Index("ix_league_invites_active", "league_id", "revoked_at", "expires_at"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    league: Mapped[League] = relationship(back_populates="invites")
    created_by: Mapped[User] = relationship()
