"""Configurable minutes threshold for statistical vote eligibility (EP07-02).

Revision ID: a2b4c6d8e088
Revises: f1a3c5e7b087
Create Date: 2026-08-17 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b4c6d8e088"
down_revision: str | Sequence[str] | None = "f1a3c5e7b087"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "league_rules",
        sa.Column(
            "minutes_threshold",
            sa.Integer(),
            nullable=False,
            server_default="15",
        ),
    )
    op.create_check_constraint(
        "ck_league_rules_minutes_threshold",
        "league_rules",
        "minutes_threshold BETWEEN 1 AND 30",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_league_rules_minutes_threshold",
        "league_rules",
        type_="check",
    )
    op.drop_column("league_rules", "minutes_threshold")
