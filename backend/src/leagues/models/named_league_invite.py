"""Invitation addressed to one fantasy coach."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import NamedInviteStatus
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User
    from leagues.models.league import League


class NamedLeagueInvite(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single-use invitation whose recipient is known."""

    __tablename__ = "named_league_invites"
    __table_args__ = (
        CheckConstraint(
            "recipient_id <> created_by_id",
            name="ck_named_league_invites_recipient_not_creator",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_named_league_invites_expiry_after_creation",
        ),
        CheckConstraint(
            "(status IN ('accepted', 'declined')) = (responded_at IS NOT NULL)",
            name="ck_named_league_invites_response_timestamp",
        ),
        CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)",
            name="ck_named_league_invites_revocation_timestamp",
        ),
        Index(
            "uq_named_league_invites_pending_recipient",
            "league_id",
            "recipient_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_named_league_invites_recipient_status",
            "recipient_id",
            "status",
            "expires_at",
        ),
        Index("ix_named_league_invites_league_status", "league_id", "status"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[NamedInviteStatus] = mapped_column(
        Enum(
            NamedInviteStatus,
            name="named_invite_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'pending'"),
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    league: Mapped[League] = relationship(back_populates="named_invites")
    recipient: Mapped[User] = relationship(foreign_keys=[recipient_id])
    created_by: Mapped[User] = relationship(foreign_keys=[created_by_id])
