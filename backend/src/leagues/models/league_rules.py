"""League rules ORM model (EP03-02)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from leagues.models.league import League


class LeagueRules(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Configurable league rules constrained by the Standard preset."""

    __tablename__ = "league_rules"
    __table_args__ = (
        UniqueConstraint("league_id", name="uq_league_rules_league_id"),
        Index("ix_league_rules_league_id", "league_id", unique=True),
        CheckConstraint(
            "participant_count BETWEEN 4 AND 10",
            name="ck_league_rules_participant_range",
        ),
        CheckConstraint("roster_size = 35", name="ck_league_rules_roster_size"),
        CheckConstraint("goalkeepers = 3", name="ck_league_rules_goalkeepers"),
        CheckConstraint("defenders = 11", name="ck_league_rules_defenders"),
        CheckConstraint("midfielders = 11", name="ck_league_rules_midfielders"),
        CheckConstraint("forwards = 10", name="ck_league_rules_forwards"),
        CheckConstraint(
            "goalkeepers + defenders + midfielders + forwards = roster_size",
            name="ck_league_rules_roster_sum",
        ),
        CheckConstraint("total_credits > 0", name="ck_league_rules_total_credits"),
        CheckConstraint(
            "min_fixtures_per_round BETWEEN 10 AND 40",
            name="ck_league_rules_min_fixtures_per_round",
        ),
        CheckConstraint(
            "turn_coverage_threshold BETWEEN 0.50 AND 1.00",
            name="ck_league_rules_turn_coverage_threshold",
        ),
        CheckConstraint(
            "minutes_threshold BETWEEN 1 AND 30",
            name="ck_league_rules_minutes_threshold",
        ),
        CheckConstraint(
            "max_automatic_substitutions BETWEEN 0 AND 5",
            name="ck_league_rules_max_automatic_substitutions",
        ),
        CheckConstraint(
            "voluntary_release_refund_percent BETWEEN 0 AND 100",
            name="ck_league_rules_voluntary_release_refund_percent",
        ),
        CheckConstraint(
            "league_exit_refund_percent BETWEEN 0 AND 100",
            name="ck_league_rules_league_exit_refund_percent",
        ),
        CheckConstraint(
            "max_active_trade_proposals_per_team >= 1",
            name="ck_league_rules_max_active_trade_proposals_per_team",
        ),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    preset_name: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'standard'"),
    )
    participant_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("8"),
    )
    roster_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("35"))
    goalkeepers: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    defenders: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("11"))
    midfielders: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("11"))
    forwards: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("10"))
    total_credits: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1000"))
    min_fixtures_per_round: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("25"),
    )
    # Frazione degli 11 titolari che ogni fantallenatore deve poter schierare
    # perché una giornata diventi un Turno Europeo valido (EP-turni-copertura).
    turn_coverage_threshold: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        server_default=text("0.75"),
    )
    minutes_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("15"),
    )
    max_automatic_substitutions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("5"),
    )
    allow_trades: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # Refund percentages for a released player, by cause (EP08-04 / FR-MKT-02).
    voluntary_release_refund_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("50"),
    )
    league_exit_refund_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("100"),
    )
    # Trade admin controls (EP08-07 / FR-MKT-03).
    require_trade_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    max_active_trade_proposals_per_team: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("10"),
    )
    allow_manual_invites: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    league: Mapped[League] = relationship(back_populates="rules")
