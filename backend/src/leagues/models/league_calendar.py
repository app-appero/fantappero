"""League H2H calendar ORM models (EP03-06)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import LeagueCalendarFormat, LeagueCalendarStatus

if TYPE_CHECKING:
    from leagues.models.league import League
    from leagues.models.league_membership import LeagueMembership


class LeagueCalendar(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Generated head-to-head calendar for one private league."""

    __tablename__ = "league_calendars"
    __table_args__ = (
        UniqueConstraint("league_id", name="uq_league_calendars_league_id"),
        Index("ix_league_calendars_league_id", "league_id", unique=True),
        CheckConstraint(
            "participant_count BETWEEN 4 AND 10",
            name="ck_league_calendars_participants",
        ),
        CheckConstraint("round_count > 0", name="ck_league_calendars_round_count"),
        CheckConstraint("matchup_count >= 0", name="ck_league_calendars_matchup_count"),
        CheckConstraint("bye_count >= 0", name="ck_league_calendars_bye_count"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[LeagueCalendarStatus] = mapped_column(
        Enum(
            LeagueCalendarStatus,
            name="league_calendar_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'draft'"),
    )
    format: Mapped[LeagueCalendarFormat] = mapped_column(
        Enum(
            LeagueCalendarFormat,
            name="league_calendar_format",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'single_round_robin'"),
    )
    algorithm_version: Mapped[str] = mapped_column(String(32), nullable=False)
    participant_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    participant_count: Mapped[int] = mapped_column(Integer, nullable=False)
    round_count: Mapped[int] = mapped_column(Integer, nullable=False)
    matchup_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bye_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    league: Mapped[League] = relationship(back_populates="calendar")
    slots: Mapped[list[LeagueCalendarSlot]] = relationship(
        back_populates="calendar",
        cascade="all, delete-orphan",
        order_by="LeagueCalendarSlot.round_number, LeagueCalendarSlot.slot_index",
    )


class LeagueCalendarSlot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One matchup or explicit bye inside a calendar round."""

    __tablename__ = "league_calendar_slots"
    __table_args__ = (
        UniqueConstraint(
            "calendar_id",
            "round_number",
            "slot_index",
            name="uq_league_calendar_slots_round_slot",
        ),
        Index("ix_league_calendar_slots_calendar_id", "calendar_id"),
        CheckConstraint("round_number > 0", name="ck_league_calendar_slots_round"),
        CheckConstraint("slot_index >= 0", name="ck_league_calendar_slots_index"),
        CheckConstraint(
            "("
            "is_bye = true AND home_membership_id IS NOT NULL AND away_membership_id IS NULL"
            ") OR ("
            "is_bye = false AND home_membership_id IS NOT NULL AND away_membership_id IS NOT NULL "
            "AND home_membership_id <> away_membership_id"
            ")",
            name="ck_league_calendar_slots_shape",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('home', 'away', 'draw')",
            name="ck_league_calendar_slots_outcome",
        ),
    )

    calendar_id: Mapped[UUID] = mapped_column(
        ForeignKey("league_calendars.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_bye: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    home_membership_id: Mapped[UUID] = mapped_column(
        ForeignKey("league_memberships.id", ondelete="CASCADE"),
        nullable=False,
    )
    away_membership_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("league_memberships.id", ondelete="CASCADE"),
        nullable=True,
    )
    home_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_fantasy_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_fantasy_goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(8), nullable=True)
    result_final: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    result_computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    calendar: Mapped[LeagueCalendar] = relationship(back_populates="slots")
    home_membership: Mapped[LeagueMembership] = relationship(
        foreign_keys=[home_membership_id],
    )
    away_membership: Mapped[LeagueMembership | None] = relationship(
        foreign_keys=[away_membership_id],
    )
