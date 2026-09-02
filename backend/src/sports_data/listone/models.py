"""ORM models for official listone roles and league overrides (EP04-04)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import FantasyRole

if TYPE_CHECKING:
    from auth.models.user import User
    from leagues.models.league import League
    from sports_data.catalog.models import Club
    from sports_data.roster.models import Athlete, SquadMembership


class RoleAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Official listone role for an athlete in a sport season year."""

    __tablename__ = "role_assignments"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id",
            "season_year",
            name="uq_role_assignments_athlete_id_season_year",
        ),
        Index("ix_role_assignments_season_year", "season_year"),
    )

    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[FantasyRole] = mapped_column(
        Enum(
            FantasyRole,
            name="fantasy_role",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    provider_position_raw: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mapping_version: Mapped[str] = mapped_column(String(32), nullable=False)
    squad_membership_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("squad_memberships.id", ondelete="SET NULL"),
        nullable=True,
    )
    club_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"),
        nullable=True,
    )

    athlete: Mapped[Athlete] = relationship()
    club: Mapped[Club | None] = relationship()
    squad_membership: Mapped[SquadMembership | None] = relationship()


class LeagueRoleOverride(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """League-scoped role override with deferred effectiveness after kickoff."""

    __tablename__ = "league_role_overrides"
    __table_args__ = (
        Index(
            "uq_league_role_overrides_active",
            "league_id",
            "athlete_id",
            unique=True,
            postgresql_where=text("superseded_at IS NULL"),
        ),
        Index("ix_league_role_overrides_league_id", "league_id"),
        Index("ix_league_role_overrides_athlete_id", "athlete_id"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[FantasyRole] = mapped_column(
        Enum(
            FantasyRole,
            name="fantasy_role",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    effective_from_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    league: Mapped[League] = relationship()
    athlete: Mapped[Athlete] = relationship()
    actor: Mapped[User] = relationship()
