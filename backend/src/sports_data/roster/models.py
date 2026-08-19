"""ORM models for athletes, squad memberships and transfers (EP04-03)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from sports_data.catalog.models import Club, SportSeason


class Athlete(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Normalized athlete profile from the sports data provider."""

    __tablename__ = "athletes"
    __table_args__ = (UniqueConstraint("provider_id", name="uq_athletes_provider_id"),)

    provider_id: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(160), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(80), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    height: Mapped[str | None] = mapped_column(String(16), nullable=True)
    weight: Mapped[str | None] = mapped_column(String(16), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    injured: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    squad_memberships: Mapped[list[SquadMembership]] = relationship(
        back_populates="athlete",
    )
    transfers: Mapped[list[Transfer]] = relationship(
        back_populates="athlete",
    )


class SquadMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Athlete membership in a club for a sport season (listone / rosa reale)."""

    __tablename__ = "squad_memberships"
    __table_args__ = (
        UniqueConstraint(
            "athlete_id",
            "club_id",
            "sport_season_id",
            name="uq_squad_memberships_athlete_id_club_id_sport_season_id",
        ),
    )

    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    club_id: Mapped[UUID] = mapped_column(
        ForeignKey("clubs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sport_season_id: Mapped[UUID] = mapped_column(
        ForeignKey("sport_seasons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shirt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_position_raw: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    ended_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'squads'"))

    athlete: Mapped[Athlete] = relationship(back_populates="squad_memberships")
    club: Mapped[Club] = relationship()
    sport_season: Mapped[SportSeason] = relationship()


class Transfer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Historical transfer record for roster reconciliation (EP04-03)."""

    __tablename__ = "transfers"
    __table_args__ = (UniqueConstraint("provider_key", name="uq_transfers_provider_key"),)

    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transfer_date: Mapped[date] = mapped_column(Date, nullable=False)
    from_club_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_club_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"),
        nullable=True,
    )
    transfer_type: Mapped[str] = mapped_column(String(64), nullable=False)
    requires_admin_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    provider_key: Mapped[str] = mapped_column(String(128), nullable=False)

    athlete: Mapped[Athlete] = relationship(back_populates="transfers")
    from_club: Mapped[Club | None] = relationship(foreign_keys=[from_club_id])
    to_club: Mapped[Club | None] = relationship(foreign_keys=[to_club_id])
