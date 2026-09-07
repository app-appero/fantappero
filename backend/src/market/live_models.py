"""ORM models for the live/ascending auction mode (EP08-09).

A live session (``MarketSession.kind == LIVE_AUCTION``) opens one athlete at a
time as a ``MarketLiveLot``. Every raise on that lot is an append-only
``MarketLiveRaise`` row — unlike sealed bids, live raises are visible to every
participant the moment they are placed. ``MarketLiveNominationQueueEntry`` is
only populated when the session's ``nomination_mode`` is ``SEQUENTIAL``.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import MarketLiveLotStatus
from database.types import UTCDateTime

if TYPE_CHECKING:
    from fantasy_teams.models import FantasyTeam
    from market.models import MarketSession
    from sports_data.roster.models import Athlete


class MarketLiveLot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One athlete on the block, one lot at a time, inside a live session."""

    __tablename__ = "market_live_lots"
    __table_args__ = (
        Index("ix_market_live_lots_session_id", "session_id"),
        Index("ix_market_live_lots_status", "session_id", "status"),
        UniqueConstraint(
            "session_id", "sequence_number", name="uq_market_live_lots_session_sequence"
        ),
        # A "passed" lot can be re-nominated later (real auction house rule); this
        # only blocks a second concurrent nomination or a second sale of the same
        # athlete within one session.
        Index(
            "uq_market_live_lots_session_athlete_active",
            "session_id",
            "athlete_id",
            unique=True,
            postgresql_where=text("status IN ('open', 'sold')"),
        ),
        CheckConstraint("current_amount_credits >= 0", name="ck_market_live_lots_amount"),
        CheckConstraint("min_increment_credits >= 1", name="ck_market_live_lots_min_increment"),
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[MarketLiveLotStatus] = mapped_column(
        Enum(
            MarketLiveLotStatus,
            name="market_live_lot_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'open'"),
    )
    opened_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("timezone('utc', now())")
    )
    closes_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    # Copied from the session's config at open time so a mid-session reconfigure
    # never retroactively changes the rules of a lot already in progress.
    min_increment_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    current_leader_team_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_amount_credits: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    session: Mapped[MarketSession] = relationship()
    athlete: Mapped[Athlete] = relationship()
    current_leader_team: Mapped[FantasyTeam | None] = relationship()
    raises: Mapped[list[MarketLiveRaise]] = relationship(
        back_populates="lot",
        cascade="all, delete-orphan",
        order_by="MarketLiveRaise.placed_at",
    )


class MarketLiveRaise(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Append-only log of every raise placed on a live lot."""

    __tablename__ = "market_live_raises"
    __table_args__ = (
        Index("ix_market_live_raises_lot_id", "lot_id", "placed_at"),
        CheckConstraint("amount_credits >= 1", name="ck_market_live_raises_amount"),
    )

    lot_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_live_lots.id", ondelete="CASCADE"),
        nullable=False,
    )
    fantasy_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    placed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=text("timezone('utc', now())")
    )

    lot: Mapped[MarketLiveLot] = relationship(back_populates="raises")
    fantasy_team: Mapped[FantasyTeam] = relationship()


class MarketLiveNominationQueueEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Pre-set nomination order for ``nomination_mode == SEQUENTIAL`` sessions."""

    __tablename__ = "market_live_nomination_queue"
    __table_args__ = (
        Index("ix_market_live_nomination_queue_session_id", "session_id"),
        UniqueConstraint(
            "session_id", "athlete_id", name="uq_market_live_nomination_queue_session_athlete"
        ),
        UniqueConstraint(
            "session_id", "position", name="uq_market_live_nomination_queue_session_position"
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    session: Mapped[MarketSession] = relationship()
    athlete: Mapped[Athlete] = relationship()
