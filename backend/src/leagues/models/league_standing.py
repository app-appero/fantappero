"""League standings ORM model (EP07-06 / FR-CLS-01)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from fantasy_teams.models import FantasyTeam
    from leagues.models.league import League


class LeagueStanding(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Classifica per squadra fantasy, sempre ricalcolata dall'origine.

    Non e' un contatore incrementale: ogni ricalcolo sovrascrive i valori a
    partire dai risultati finali persistiti (FR-CLS-01), cosi' un ricalcolo
    non puo' mai duplicare partite o punti.
    """

    __tablename__ = "league_standings"
    __table_args__ = (
        UniqueConstraint(
            "league_id",
            "fantasy_team_id",
            name="uq_league_standings_league_id_fantasy_team_id",
        ),
        Index("ix_league_standings_league_id", "league_id"),
        CheckConstraint("played >= 0", name="ck_league_standings_played"),
        CheckConstraint("won + drawn + lost = played", name="ck_league_standings_record_sum"),
        CheckConstraint("position >= 1", name="ck_league_standings_position"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    fantasy_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    played: Mapped[int] = mapped_column(Integer, nullable=False)
    won: Mapped[int] = mapped_column(Integer, nullable=False)
    drawn: Mapped[int] = mapped_column(Integer, nullable=False)
    lost: Mapped[int] = mapped_column(Integer, nullable=False)
    fantasy_goals_for: Mapped[int] = mapped_column(Integer, nullable=False)
    fantasy_goals_against: Mapped[int] = mapped_column(Integer, nullable=False)
    # Fantapunti aggregati (EP13-P02): somma dei punti di formazione fatti e
    # subiti. Default 0 per retrocompatibilita' con le righe gia' persistite,
    # che vengono comunque riscritte al primo ricalcolo.
    fantasy_points_for: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0", default=0.0
    )
    fantasy_points_against: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0", default=0.0
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    league: Mapped[League] = relationship()
    fantasy_team: Mapped[FantasyTeam] = relationship()
