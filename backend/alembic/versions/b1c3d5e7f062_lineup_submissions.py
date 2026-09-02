"""Lineup submissions for approved modules (EP06-02).

Revision ID: b1c3d5e7f062
Revises: a0b1c2d3e070
Create Date: 2026-08-14 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b1c3d5e7f062"
down_revision: str | Sequence[str] | None = "a0b1c2d3e070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

fantasy_module = postgresql.ENUM(
    "3-4-3",
    "3-5-2",
    "4-3-3",
    "4-4-2",
    "4-5-1",
    "5-3-2",
    "5-4-1",
    name="fantasy_module",
    create_type=False,
)

lineup_slot_kind = postgresql.ENUM(
    "starter",
    "bench",
    name="lineup_slot_kind",
    create_type=False,
)

fantasy_role = postgresql.ENUM(
    "P",
    "D",
    "C",
    "A",
    name="fantasy_role",
    create_type=False,
)


def upgrade() -> None:
    op.execute("ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS 'fantasy_lineup_saved';")

    fantasy_module.create(op.get_bind(), checkfirst=True)
    lineup_slot_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "lineup_submissions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("league_id", sa.UUID(), nullable=False),
        sa.Column("round_id", sa.UUID(), nullable=False),
        sa.Column("fantasy_team_id", sa.UUID(), nullable=False),
        sa.Column("module", fantasy_module, nullable=False),
        sa.Column("revision", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_lineup_submissions_revision")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["round_id"], ["fantasy_rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fantasy_team_id"], ["fantasy_teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lineup_submissions")),
        sa.UniqueConstraint(
            "round_id",
            "fantasy_team_id",
            name="uq_lineup_submissions_round_id_fantasy_team_id",
        ),
    )
    op.create_index("ix_lineup_submissions_league_id", "lineup_submissions", ["league_id"])
    op.create_index(
        "ix_lineup_submissions_fantasy_team_id",
        "lineup_submissions",
        ["fantasy_team_id"],
    )

    op.create_table(
        "lineup_players",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("submission_id", sa.UUID(), nullable=False),
        sa.Column("athlete_id", sa.UUID(), nullable=False),
        sa.Column("slot_kind", lineup_slot_kind, nullable=False),
        sa.Column("role", fantasy_role, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint("sort_order >= 0", name=op.f("ck_lineup_players_sort_order")),
        sa.ForeignKeyConstraint(["submission_id"], ["lineup_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["athlete_id"], ["athletes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lineup_players")),
        sa.UniqueConstraint(
            "submission_id",
            "athlete_id",
            name="uq_lineup_players_submission_id_athlete_id",
        ),
        sa.UniqueConstraint(
            "submission_id",
            "slot_kind",
            "sort_order",
            name="uq_lineup_players_submission_slot_order",
        ),
    )
    op.create_index("ix_lineup_players_athlete_id", "lineup_players", ["athlete_id"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_lineup_players_athlete_id")
    op.execute("DROP TABLE IF EXISTS lineup_players")
    op.execute("DROP INDEX IF EXISTS ix_lineup_submissions_fantasy_team_id")
    op.execute("DROP INDEX IF EXISTS ix_lineup_submissions_league_id")
    op.execute("DROP TABLE IF EXISTS lineup_submissions")
    lineup_slot_kind.drop(op.get_bind(), checkfirst=True)
    fantasy_module.drop(op.get_bind(), checkfirst=True)
    op.execute(
        sa.text("DELETE FROM league_audit_events WHERE action::text IN ('fantasy_lineup_saved')")
    )
