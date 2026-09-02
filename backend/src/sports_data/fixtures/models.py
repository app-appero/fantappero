"""ORM models for fixtures, match events, lineups and player stats (EP04-05)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.types import UTCDateTime

if TYPE_CHECKING:
    from sports_data.catalog.models import Club, SportSeason
    from sports_data.roster.models import Athlete


class Fixture(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Normalized match calendar row from the sports data provider."""

    __tablename__ = "fixtures"
    __table_args__ = (UniqueConstraint("provider_id", name="uq_fixtures_provider_id"),)

    provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sport_season_id: Mapped[UUID] = mapped_column(
        ForeignKey("sport_seasons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    home_club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    away_club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    kickoff_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    status_short: Mapped[str] = mapped_column(String(16), nullable=False)
    status_elapsed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    home_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    round_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    venue_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    venue_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    referee: Mapped[str | None] = mapped_column(String(160), nullable=True)

    sport_season: Mapped[SportSeason] = relationship()
    home_club: Mapped[Club] = relationship(foreign_keys=[home_club_id])
    away_club: Mapped[Club] = relationship(foreign_keys=[away_club_id])
    match_events: Mapped[list[MatchEvent]] = relationship(back_populates="fixture")
    official_lineups: Mapped[list[OfficialLineup]] = relationship(back_populates="fixture")
    player_match_stats: Mapped[list[PlayerMatchStat]] = relationship(back_populates="fixture")


class MatchEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Timeline / scoring event keyed by ``provider_event_key`` (idempotent)."""

    __tablename__ = "match_events"
    __table_args__ = (
        UniqueConstraint("provider_event_key", name="uq_match_events_provider_event_key"),
    )

    provider_event_key: Mapped[str] = mapped_column(String(256), nullable=False)
    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    related_athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
    )
    club_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"),
        nullable=True,
    )
    athlete_provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    related_athlete_provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    club_provider_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    event_detail: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scoring_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'timeline'"),
    )
    minute_elapsed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minute_extra: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    anomaly_codes: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    retracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    fixture: Mapped[Fixture] = relationship(back_populates="match_events")
    athlete: Mapped[Athlete | None] = relationship(foreign_keys=[athlete_id])
    related_athlete: Mapped[Athlete | None] = relationship(foreign_keys=[related_athlete_id])
    club: Mapped[Club | None] = relationship()


class OfficialLineup(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Official lineup snapshot for one club in a fixture."""

    __tablename__ = "official_lineups"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id",
            "club_id",
            name="uq_official_lineups_fixture_id_club_id",
        ),
    )

    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    formation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    coach_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # Istante di acquisizione dal provider (EP13-P05 / ADR-0005). Distinto da
    # `updated_at`, che cambia a ogni ri-sincronizzazione: senza questo campo
    # non si potrebbe dimostrare che la formazione automatica IA non ha usato
    # dati arrivati dopo il lock.
    fetched_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    fixture: Mapped[Fixture] = relationship(back_populates="official_lineups")
    club: Mapped[Club] = relationship()
    entries: Mapped[list[OfficialLineupEntry]] = relationship(
        back_populates="lineup",
        cascade="all, delete-orphan",
    )


class OfficialLineupEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Player entry in an official lineup (starter or substitute)."""

    __tablename__ = "official_lineup_entries"
    __table_args__ = (
        UniqueConstraint(
            "lineup_id",
            "athlete_provider_id",
            name="uq_official_lineup_entries_lineup_id_athlete_provider_id",
        ),
    )

    lineup_id: Mapped[UUID] = mapped_column(
        ForeignKey("official_lineups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    athlete_provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_starter: Mapped[bool] = mapped_column(Boolean, nullable=False)
    shirt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_raw: Mapped[str | None] = mapped_column(String(16), nullable=True)
    grid: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    lineup: Mapped[OfficialLineup] = relationship(back_populates="entries")
    athlete: Mapped[Athlete | None] = relationship()


class PlayerMatchStat(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-player match statistics (minutes, rating, raw stats JSON)."""

    __tablename__ = "player_match_stats"
    __table_args__ = (
        UniqueConstraint(
            "fixture_id",
            "athlete_provider_id",
            name="uq_player_match_stats_fixture_id_athlete_provider_id",
        ),
    )

    fixture_id: Mapped[UUID] = mapped_column(
        ForeignKey("fixtures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    athlete_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("athletes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    athlete_provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    club_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"),
        nullable=True,
    )
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position_raw: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_substitute: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    provider_rating: Mapped[str | None] = mapped_column(String(16), nullable=True)
    stats_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    stats_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    fixture: Mapped[Fixture] = relationship(back_populates="player_match_stats")
    athlete: Mapped[Athlete | None] = relationship()
    club: Mapped[Club | None] = relationship()
