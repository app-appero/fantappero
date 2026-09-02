"""League ORM model (EP02-01 / EP03-01)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import LeagueState

if TYPE_CHECKING:
    from leagues.models.competition import Competition
    from leagues.models.league_calendar import LeagueCalendar
    from leagues.models.league_invite import LeagueInvite
    from leagues.models.league_membership import LeagueMembership
    from leagues.models.league_rules import LeagueRules
    from leagues.models.named_league_invite import NamedLeagueInvite


class League(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Private fantasy league (tenant boundary)."""

    __tablename__ = "leagues"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[LeagueState] = mapped_column(
        Enum(
            LeagueState,
            name="league_state",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'draft'"),
    )

    memberships: Mapped[list[LeagueMembership]] = relationship(
        back_populates="league",
        cascade="all, delete-orphan",
    )
    invites: Mapped[list[LeagueInvite]] = relationship(
        back_populates="league",
        cascade="all, delete-orphan",
    )
    named_invites: Mapped[list[NamedLeagueInvite]] = relationship(
        back_populates="league",
        cascade="all, delete-orphan",
    )
    competitions: Mapped[list[Competition]] = relationship(
        secondary="league_competitions",
        back_populates="leagues",
    )
    rules: Mapped[LeagueRules | None] = relationship(
        back_populates="league",
        cascade="all, delete-orphan",
        uselist=False,
    )
    calendar: Mapped[LeagueCalendar | None] = relationship(
        back_populates="league",
        cascade="all, delete-orphan",
        uselist=False,
    )
