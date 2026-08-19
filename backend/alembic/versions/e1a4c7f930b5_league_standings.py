"""League standings table (EP07-06).

Revision ID: e1a4c7f930b5
Revises: d8f1a4c6e723
Create Date: 2026-08-17 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1a4c7f930b5"
down_revision: str | Sequence[str] | None = "d8f1a4c6e723"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "league_standings",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("league_id", sa.UUID(), nullable=False),
        sa.Column("fantasy_team_id", sa.UUID(), nullable=False),
        sa.Column("played", sa.Integer(), nullable=False),
        sa.Column("won", sa.Integer(), nullable=False),
        sa.Column("drawn", sa.Integer(), nullable=False),
        sa.Column("lost", sa.Integer(), nullable=False),
        sa.Column("fantasy_goals_for", sa.Integer(), nullable=False),
        sa.Column("fantasy_goals_against", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("played >= 0", name=op.f("ck_league_standings_played")),
        sa.CheckConstraint(
            "won + drawn + lost = played", name=op.f("ck_league_standings_record_sum")
        ),
        sa.CheckConstraint("position >= 1", name=op.f("ck_league_standings_position")),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fantasy_team_id"], ["fantasy_teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_league_standings")),
        sa.UniqueConstraint(
            "league_id",
            "fantasy_team_id",
            name="uq_league_standings_league_id_fantasy_team_id",
        ),
    )
    op.create_index("ix_league_standings_league_id", "league_standings", ["league_id"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_league_standings_league_id")
    op.execute("DROP TABLE IF EXISTS league_standings")
