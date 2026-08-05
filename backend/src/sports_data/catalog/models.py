"""ORM models for SPD sports catalog (competitions reuse leagues.Competition)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from leagues.models.competition import Competition


class Club(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Normalized club (team) from the sports data provider."""

    __tablename__ = "clubs"
    __table_args__ = (UniqueConstraint("provider_id", name="uq_clubs_provider_id"),)

    provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    country: Mapped[str | None] = mapped_column(String(80), nullable=True)
    national: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )

    season_memberships: Mapped[list[CompetitionSeasonClub]] = relationship(
        back_populates="club",
    )


class SportSeason(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Provider season under a competition (year + coverage gates)."""

    __tablename__ = "sport_seasons"
    __table_args__ = (
        UniqueConstraint(
            "competition_id",
            "year",
            name="uq_sport_seasons_competition_id_year",
        ),
    )

    competition_id: Mapped[UUID] = mapped_column(
        ForeignKey("competitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    coverage_events: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    coverage_lineups: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    coverage_statistics_players: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    coverage_injuries: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    coverage_predictions: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    coverage_standings: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    competition: Mapped[Competition] = relationship()
    club_memberships: Mapped[list[CompetitionSeasonClub]] = relationship(
        back_populates="sport_season",
    )


class CompetitionSeasonClub(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Club membership in a competition season (from ``/teams?league&season``)."""

    __tablename__ = "competition_season_clubs"
    __table_args__ = (
        UniqueConstraint(
            "sport_season_id",
            "club_id",
            name="uq_competition_season_clubs_sport_season_id_club_id",
        ),
    )

    sport_season_id: Mapped[UUID] = mapped_column(
        ForeignKey("sport_seasons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sport_season: Mapped[SportSeason] = relationship(back_populates="club_memberships")
    club: Mapped[Club] = relationship(back_populates="season_memberships")
