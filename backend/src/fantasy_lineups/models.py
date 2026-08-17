"""ORM models for lineup submissions, drafts and tactical moves."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.enums import FantasyModule, FantasyRole, LineupSlotKind, TacticalMoveStatus
from database.types import UTCDateTime

if TYPE_CHECKING:
    from auth.models.user import User
    from fantasy_teams.models import FantasyTeam
    from fantasy_turns.models import FantasyRound
    from leagues.models.league import League
    from sports_data.roster.models import Athlete


class LineupSubmission(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Current formation for one fantasy team in one european turn."""

    __tablename__ = "lineup_submissions"
    __table_args__ = (
        UniqueConstraint(
            "round_id",
            "fantasy_team_id",
            name="uq_lineup_submissions_round_id_fantasy_team_id",
        ),
        CheckConstraint("revision >= 1", name="ck_lineup_submissions_revision"),
        Index("ix_lineup_submissions_league_id", "league_id"),
        Index("ix_lineup_submissions_fantasy_team_id", "fantasy_team_id"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_rounds.id", ondelete="CASCADE"),
        nullable=False,
    )
    fantasy_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    module: Mapped[FantasyModule] = mapped_column(
        Enum(
            FantasyModule,
            name="fantasy_module",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    submitted_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    league: Mapped[League] = relationship()
    round: Mapped[FantasyRound] = relationship()
    fantasy_team: Mapped[FantasyTeam] = relationship()
    submitted_by: Mapped[User] = relationship()
    players: Mapped[list[LineupPlayer]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="LineupPlayer.sort_order",
    )
    tactical_moves: Mapped[list[TacticalMove]] = relationship(
        back_populates="submission",
        cascade="all, delete-orphan",
        order_by="TacticalMove.sequence",
    )


class LineupDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Work-in-progress formation for one fantasy team in one european turn."""

    __tablename__ = "lineup_drafts"
    __table_args__ = (
        UniqueConstraint(
            "round_id",
            "fantasy_team_id",
            name="uq_lineup_drafts_round_id_fantasy_team_id",
        ),
        Index("ix_lineup_drafts_league_id", "league_id"),
        Index("ix_lineup_drafts_fantasy_team_id", "fantasy_team_id"),
    )

    league_id: Mapped[UUID] = mapped_column(
        ForeignKey("leagues.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_rounds.id", ondelete="CASCADE"),
        nullable=False,
    )
    fantasy_team_id: Mapped[UUID] = mapped_column(
        ForeignKey("fantasy_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    module: Mapped[FantasyModule] = mapped_column(
        Enum(
            FantasyModule,
            name="fantasy_module",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    starter_athlete_ids: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    bench_athlete_ids: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    saved_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    saved_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    copy_source_round_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fantasy_rounds.id", ondelete="SET NULL"),
        nullable=True,
    )

    league: Mapped[League] = relationship()
    round: Mapped[FantasyRound] = relationship(foreign_keys=[round_id])
    fantasy_team: Mapped[FantasyTeam] = relationship()
    saved_by: Mapped[User] = relationship()
    copy_source_round: Mapped[FantasyRound | None] = relationship(
        foreign_keys=[copy_source_round_id]
    )


class LineupPlayer(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Starter or bench player in a saved lineup."""

    __tablename__ = "lineup_players"
    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            "athlete_id",
            name="uq_lineup_players_submission_id_athlete_id",
        ),
        UniqueConstraint(
            "submission_id",
            "slot_kind",
            "sort_order",
            name="uq_lineup_players_submission_slot_order",
        ),
        CheckConstraint("sort_order >= 0", name="ck_lineup_players_sort_order"),
        Index("ix_lineup_players_athlete_id", "athlete_id"),
    )

    submission_id: Mapped[UUID] = mapped_column(
        ForeignKey("lineup_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    athlete_id: Mapped[UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="RESTRICT"),
        nullable=False,
    )
    slot_kind: Mapped[LineupSlotKind] = mapped_column(
        Enum(
            LineupSlotKind,
            name="lineup_slot_kind",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
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
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    submission: Mapped[LineupSubmission] = relationship(back_populates="players")
    athlete: Mapped[Athlete] = relationship()


class TacticalMove(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Recorded tactical move for a saved lineup (max 3 per turn)."""

    __tablename__ = "tactical_moves"
    __table_args__ = (
        UniqueConstraint(
            "submission_id",
            "sequence",
            name="uq_tactical_moves_submission_id_sequence",
        ),
        CheckConstraint(
            "sequence >= 1 AND sequence <= 3",
            name="ck_tactical_moves_sequence",
        ),
        Index("ix_tactical_moves_submission_id", "submission_id"),
    )

    submission_id: Mapped[UUID] = mapped_column(
        ForeignKey("lineup_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TacticalMoveStatus] = mapped_column(
        Enum(
            TacticalMoveStatus,
            name="tactical_move_status",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        server_default=text("'applied'"),
    )
    from_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    to_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    used_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    submission: Mapped[LineupSubmission] = relationship(back_populates="tactical_moves")
    used_by: Mapped[User] = relationship()
