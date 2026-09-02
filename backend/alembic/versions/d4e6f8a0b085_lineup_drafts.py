"""Lineup drafts and copy/draft audit actions (EP06-06).

Revision ID: d4e6f8a0b085
Revises: c3e5f7a9b074
Create Date: 2026-08-14 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e6f8a0b085"
down_revision: str | Sequence[str] | None = "c3e5f7a9b074"
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


def upgrade() -> None:
    for action in ("fantasy_lineup_copied", "fantasy_lineup_draft_saved"):
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    op.create_table(
        "lineup_drafts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fantasy_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module", fantasy_module, nullable=False),
        sa.Column(
            "starter_athlete_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "bench_athlete_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("saved_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("copy_source_round_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["round_id"], ["fantasy_rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fantasy_team_id"], ["fantasy_teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["saved_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["copy_source_round_id"],
            ["fantasy_rounds.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lineup_drafts"),
        sa.UniqueConstraint(
            "round_id",
            "fantasy_team_id",
            name="uq_lineup_drafts_round_id_fantasy_team_id",
        ),
    )
    op.create_index("ix_lineup_drafts_league_id", "lineup_drafts", ["league_id"])
    op.create_index("ix_lineup_drafts_fantasy_team_id", "lineup_drafts", ["fantasy_team_id"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_lineup_drafts_fantasy_team_id")
    op.execute("DROP INDEX IF EXISTS ix_lineup_drafts_league_id")
    op.execute("DROP TABLE IF EXISTS lineup_drafts")
    op.execute(
        sa.text(
            "DELETE FROM league_audit_events WHERE action::text IN "
            "('fantasy_lineup_copied', 'fantasy_lineup_draft_saved')"
        )
    )
