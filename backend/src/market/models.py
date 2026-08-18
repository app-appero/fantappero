"""ORM models for the sealed-bid market session and its bids (EP08-01)."""

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import MarketBidStatus, MarketSessionKind, MarketSessionStatus, TradeStatus
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User
    from fantasy_teams.models import FantasyTeam
    from leagues.models.league import League
    from sports_data.roster.models import Athlete


class MarketSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sealed-bid market window (initial auction; waiver reuses this in EP08-03)."""

    __tablename__ = "market_sessions"
    __table_args__ = (
        Index("ix_market_sessions_league_id", "league_id"),
        Index("ix_market_sessions_status", "status"),
        CheckConstraint("closes_at > opens_at", name="ck_market_sessions_window_order"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[MarketSessionKind] = mapped_column(
        Enum(
            MarketSessionKind,
            name="market_session_kind",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[MarketSessionStatus] = mapped_column(
        Enum(
            MarketSessionStatus,
            name="market_session_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'scheduled'"),
    )
    opens_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Tiebreak child sessions only (EP08-02): the round they were reopened from.
    parent_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("market_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Tiebreak child sessions only: restricts bidding to this single athlete.
    target_athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=True,
    )
    # Tiebreak child sessions only: restricts bidding to these fantasy team ids.
    eligible_team_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    league: Mapped[League] = relationship()
    creator: Mapped[User | None] = relationship()
    parent_session: Mapped[MarketSession | None] = relationship(
        remote_side="MarketSession.id",
        foreign_keys=[parent_session_id],
    )
    bids: Mapped[list[MarketBid]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class MarketBid(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Sealed offer for one athlete inside a market session (EP08-01)."""

    __tablename__ = "market_bids"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "fantasy_team_id",
            "athlete_id",
            name="uq_market_bids_session_team_athlete",
        ),
        Index("ix_market_bids_session_id", "session_id"),
        Index("ix_market_bids_athlete_id", "athlete_id"),
        Index("ix_market_bids_fantasy_team_id", "fantasy_team_id"),
        CheckConstraint("amount_credits >= 1", name="ck_market_bids_amount_credits"),
    )

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("market_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    fantasy_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount_credits: Mapped[int] = mapped_column(Integer, nullable=False)
    # Waiver bids only (EP08-03 / FR-MKT-01): the roster player the team commits to
    # release if this bid wins. Never set on initial-auction bids.
    release_athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[MarketBidStatus] = mapped_column(
        Enum(
            MarketBidStatus,
            name="market_bid_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'submitted'"),
    )
    submitted_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=text("timezone('utc', now())"),
    )

    session: Mapped[MarketSession] = relationship(back_populates="bids")
    fantasy_team: Mapped[FantasyTeam] = relationship()
    athlete: Mapped[Athlete] = relationship(foreign_keys=[athlete_id])
    release_athlete: Mapped[Athlete | None] = relationship(foreign_keys=[release_athlete_id])


class TradeProposal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One-to-one trade proposal between two fantasy teams (EP08-05 / FR-MKT-03)."""

    __tablename__ = "trade_proposals"
    __table_args__ = (
        Index("ix_trade_proposals_league_id", "league_id"),
        Index("ix_trade_proposals_proposer_team_id", "proposer_team_id"),
        Index("ix_trade_proposals_recipient_team_id", "recipient_team_id"),
        Index("ix_trade_proposals_status", "status"),
        CheckConstraint("offered_credits >= 0", name="ck_trade_proposals_offered_credits"),
        CheckConstraint("requested_credits >= 0", name="ck_trade_proposals_requested_credits"),
        CheckConstraint(
            "proposer_team_id != recipient_team_id",
            name="ck_trade_proposals_distinct_teams",
        ),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposer_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Athlete UUIDs stored as JSONB string arrays: a trade side can carry several
    # players, and the set is only meaningful together with the paired credits.
    offered_athlete_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    requested_athlete_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    offered_credits: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    requested_credits: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    status: Mapped[TradeStatus] = mapped_column(
        Enum(
            TradeStatus,
            name="trade_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'proposed'"),
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    league: Mapped[League] = relationship()
    proposer_team: Mapped[FantasyTeam] = relationship(foreign_keys=[proposer_team_id])
    recipient_team: Mapped[FantasyTeam] = relationship(foreign_keys=[recipient_team_id])
    creator: Mapped[User | None] = relationship()
