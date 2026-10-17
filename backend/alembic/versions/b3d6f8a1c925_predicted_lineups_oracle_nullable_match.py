"""predicted_lineup_snapshots.fotmob_match_id nullable (Soccer-Oracle snapshots).

Revision ID: b3d6f8a1c925
Revises: a8c4e2b7d1f3
Create Date: 2026-10-17 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3d6f8a1c925"
down_revision: str | Sequence[str] | None = "a8c4e2b7d1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "predicted_lineup_snapshots",
        "fotmob_match_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE predicted_lineup_snapshots SET fotmob_match_id = 0 WHERE fotmob_match_id IS NULL"
    )
    op.alter_column(
        "predicted_lineup_snapshots",
        "fotmob_match_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
