"""ORM models for european fantasy turns (EP06-01)."""

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
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import (
    FantasyRoundFixtureReason,
    FantasyRoundHomologationStatus,
    FantasyTurnKind,
    FantasyTurnStatus,
)
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User
    from leagues.models.league import League
    from sports_data.fixtures.models import Fixture


class FantasyRound(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """FantApperò european turn grouping real fixtures in a temporal window."""

    __tablename__ = "fantasy_rounds"
    __table_args__ = (
        UniqueConstraint("league_id", "number", name="uq_fantasy_rounds_league_number"),
        CheckConstraint("number >= 1", name="ck_fantasy_rounds_number"),
        CheckConstraint(
            "window_end_at > window_start_at",
            name="ck_fantasy_rounds_window_order",
        ),
        Index("ix_fantasy_rounds_league_id", "league_id"),
        Index("ix_fantasy_rounds_status", "status"),
        Index(
            "ix_fantasy_rounds_window",
            "league_id",
            "window_start_at",
            "window_end_at",
        ),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[FantasyTurnKind] = mapped_column(
        Enum(
            FantasyTurnKind,
            name="fantasy_turn_kind",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    window_start_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    window_end_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    opens_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    cutoff_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status: Mapped[FantasyTurnStatus] = mapped_column(
        Enum(
            FantasyTurnStatus,
            name="fantasy_turn_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'scheduled'"),
    )
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    homologation_status: Mapped[FantasyRoundHomologationStatus] = mapped_column(
        Enum(
            FantasyRoundHomologationStatus,
            name="fantasy_round_homologation_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'provisional'"),
    )
    homologated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    homologated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    homologation_formula_version: Mapped[str | None] = mapped_column(Text, nullable=True)

    league: Mapped[League] = relationship()
    homologated_by: Mapped[User | None] = relationship()
    fixtures: Mapped[list[FantasyRoundFixture]] = relationship(
        back_populates="round",
        cascade="all, delete-orphan",
    )


class FantasyRoundFixture(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Link between a fantasy turn and a real sports fixture."""

    __tablename__ = "fantasy_round_fixtures"
    __table_args__ = (
        UniqueConstraint(
            "round_id",
            "fixture_id",
            name="uq_fantasy_round_fixtures_round_fixture",
        ),
        Index("ix_fantasy_round_fixtures_round_id", "round_id"),
        Index("ix_fantasy_round_fixtures_league_id", "league_id"),
        Index("ix_fantasy_round_fixtures_fixture_id", "fixture_id"),
        Index(
            "uq_fantasy_round_fixtures_active_league_fixture",
            "league_id",
            "fixture_id",
            unique=True,
            postgresql_where=text("excluded_at IS NULL"),
        ),
    )

    round_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_rounds.id", ondelete="CASCADE"),
        nullable=False,
    )
    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="RESTRICT"),
        nullable=False,
    )
    included_reason: Mapped[FantasyRoundFixtureReason] = mapped_column(
        Enum(
            FantasyRoundFixtureReason,
            name="fantasy_round_fixture_reason",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'window'"),
    )
    excluded_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    excluded_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    observed_kickoff_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    lock_latched_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    round: Mapped[FantasyRound] = relationship(back_populates="fixtures")
    fixture: Mapped[Fixture] = relationship()
    excluded_by: Mapped[User | None] = relationship()
