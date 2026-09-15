"""League-admin market window toggle (rosa/asta).

The transfer window for roster moves and auctions is opened and closed by the
league admin. Trades stay available regardless of this flag. Existing leagues
inherit the open default so current setup and tests keep working.

Revision ID: e4a8c2d6f019
Revises: d0a2c4e6f813
Create Date: 2026-09-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4a8c2d6f019"
down_revision: str | Sequence[str] | None = "d0a2c4e6f813"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leagues",
        sa.Column(
            "market_open",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.execute(
        "ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS 'market_gate_toggled';"
    )


def downgrade() -> None:
    op.drop_column("leagues", "market_open")
