"""Configurable substitution limit and effective lineups (EP07-04).

Revision ID: c7e9f2a5b410
Revises: b4d6f8a1c239
Create Date: 2026-08-17 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7e9f2a5b410"
down_revision: str | Sequence[str] | None = "b4d6f8a1c239"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Reuses the existing type created in b1c3d5e7f062 (EP06-02): not owned here.
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
    op.add_column(
        "league_rules",
        sa.Column(
            "max_automatic_substitutions",
            sa.Integer(),
            server_default=sa.text("5"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_league_rules_max_automatic_substitutions",
        "league_rules",
        "max_automatic_substitutions BETWEEN 0 AND 5",
    )

    op.create_table(
        "effective_lineups",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("league_id", sa.UUID(), nullable=False),
        sa.Column("round_id", sa.UUID(), nullable=False),
        sa.Column("fantasy_team_id", sa.UUID(), nullable=False),
        sa.Column("submission_id", sa.UUID(), nullable=False),
        sa.Column("module", fantasy_module, nullable=False),
        sa.Column("module_valid", sa.Boolean(), nullable=False),
        sa.Column("max_automatic_substitutions", sa.Integer(), nullable=False),
        sa.Column("effective_starter_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "substitutions_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "skipped_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["round_id"], ["fantasy_rounds.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fantasy_team_id"], ["fantasy_teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["lineup_submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_effective_lineups")),
        sa.UniqueConstraint(
            "round_id",
            "fantasy_team_id",
            name="uq_effective_lineups_round_id_fantasy_team_id",
        ),
    )
    op.create_index("ix_effective_lineups_league_id", "effective_lineups", ["league_id"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_effective_lineups_league_id")
    op.execute("DROP TABLE IF EXISTS effective_lineups")
    op.drop_constraint(
        "ck_league_rules_max_automatic_substitutions",
        "league_rules",
        type_="check",
    )
    op.drop_column("league_rules", "max_automatic_substitutions")
