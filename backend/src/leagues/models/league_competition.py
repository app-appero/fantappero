"""League-to-competition association (EP03-01)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class LeagueCompetition(Base):
    """Selected competitions for a private league."""

    __tablename__ = "league_competitions"

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        primary_key=True,
    )
    competition_id: Mapped[UUID] = mapped_column(
        ForeignKey("competitions.id", ondelete="RESTRICT"),
        primary_key=True,
    )
