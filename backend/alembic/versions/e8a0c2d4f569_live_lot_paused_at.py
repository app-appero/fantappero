"""Pausa del timer del lotto live a mercato chiuso.

Revision ID: e8a0c2d4f569
Revises: d7f9b1c3e458
Create Date: 2026-11-18 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8a0c2d4f569"
down_revision: str | Sequence[str] | None = "d7f9b1c3e458"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_live_lots", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("market_live_lots", "paused_at")
