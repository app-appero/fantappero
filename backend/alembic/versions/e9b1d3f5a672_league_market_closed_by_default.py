"""Mercato chiuso di default per le leghe nuove (decisione del 20/11/2026).

Il mercato si apre solo quando la lega è al completo e lo accende l'amministratore: una lega
nuova nasce quindi con ``market_open = false``. Cambia solo il default della colonna; le leghe
esistenti tengono il valore salvato dell'interruttore.

Revision ID: e9b1d3f5a672
Revises: e8a0c2d4f569
Create Date: 2026-11-20 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e9b1d3f5a672"
down_revision: str | Sequence[str] | None = "e8a0c2d4f569"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "leagues",
        "market_open",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.text("false"),
    )


def downgrade() -> None:
    op.alter_column(
        "leagues",
        "market_open",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        server_default=sa.text("true"),
    )
