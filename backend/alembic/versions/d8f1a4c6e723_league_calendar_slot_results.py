"""H2H match results on league_calendar_slots (EP07-05).

Revision ID: d8f1a4c6e723
Revises: c7e9f2a5b410
Create Date: 2026-08-17 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f1a4c6e723"
down_revision: str | Sequence[str] | None = "c7e9f2a5b410"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("league_calendar_slots", sa.Column("home_score", sa.Float(), nullable=True))
    op.add_column("league_calendar_slots", sa.Column("away_score", sa.Float(), nullable=True))
    op.add_column(
        "league_calendar_slots", sa.Column("home_fantasy_goals", sa.Integer(), nullable=True)
    )
    op.add_column(
        "league_calendar_slots", sa.Column("away_fantasy_goals", sa.Integer(), nullable=True)
    )
    op.add_column("league_calendar_slots", sa.Column("outcome", sa.String(length=8), nullable=True))
    op.add_column(
        "league_calendar_slots",
        sa.Column(
            "result_final",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "league_calendar_slots",
        sa.Column("result_computed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_league_calendar_slots_outcome",
        "league_calendar_slots",
        "outcome IS NULL OR outcome IN ('home', 'away', 'draw')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_league_calendar_slots_outcome",
        "league_calendar_slots",
        type_="check",
    )
    op.drop_column("league_calendar_slots", "result_computed_at")
    op.drop_column("league_calendar_slots", "result_final")
    op.drop_column("league_calendar_slots", "outcome")
    op.drop_column("league_calendar_slots", "away_fantasy_goals")
    op.drop_column("league_calendar_slots", "home_fantasy_goals")
    op.drop_column("league_calendar_slots", "away_score")
    op.drop_column("league_calendar_slots", "home_score")
