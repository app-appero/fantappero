"""Bonus/malus scoring columns on player_match_ratings (EP07-03).

Revision ID: b4d6f8a1c239
Revises: a2b4c6d8e088
Create Date: 2026-08-17 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4d6f8a1c239"
down_revision: str | Sequence[str] | None = "a2b4c6d8e088"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "player_match_ratings",
        sa.Column("bonus_config_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "player_match_ratings",
        sa.Column(
            "bonus_malus_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "player_match_ratings",
        sa.Column(
            "bonus_malus_total",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "player_match_ratings",
        sa.Column("fantasy_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("player_match_ratings", "fantasy_score")
    op.drop_column("player_match_ratings", "bonus_malus_total")
    op.drop_column("player_match_ratings", "bonus_malus_json")
    op.drop_column("player_match_ratings", "bonus_config_version")
