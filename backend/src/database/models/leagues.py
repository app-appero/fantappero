"""League models for membership authorization and configuration (EP02-01, EP03-01)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TableNameMixin, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import LeagueMemberRole, LeagueState

if TYPE_CHECKING:
    from database.models.competitions import Competition

league_member_role_enum = ENUM(
    LeagueMemberRole,
    name="league_member_role",
    create_type=False,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)

league_state_enum = ENUM(
    LeagueState,
    name="league_state",
    create_type=False,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)

league_competitions = Table(
    "league_competitions",
    Base.metadata,
    Column("league_id", ForeignKey("leagues.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "competition_id",
        ForeignKey("competitions.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
)


class League(UUIDPrimaryKeyMixin, TimestampMixin, TableNameMixin, Base):
    """Fantasy league container with draft configuration (EP03-01)."""

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[LeagueState] = mapped_column(
        league_state_enum,
        nullable=False,
        default=LeagueState.DRAFT,
    )

    memberships: Mapped[list[LeagueMembership]] = relationship(back_populates="league")
    competitions: Mapped[list[Competition]] = relationship(secondary=league_competitions)


class LeagueMembership(UUIDPrimaryKeyMixin, TimestampMixin, TableNameMixin, Base):
    """User membership in a league."""

    __table_args__ = (
        UniqueConstraint("league_id", "user_id", name="uq_league_memberships_league_id_user_id"),
    )

    league_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[LeagueMemberRole] = mapped_column(
        league_member_role_enum,
        nullable=False,
        default=LeagueMemberRole.MEMBER,
    )
    historical_display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)

    league: Mapped[League] = relationship(back_populates="memberships")
