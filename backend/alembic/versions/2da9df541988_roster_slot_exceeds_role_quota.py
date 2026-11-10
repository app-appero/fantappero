"""Slot di rosa oltre la quota di ruolo, in attesa di risoluzione (EP08-10).

Uno scambio accettato può portare una squadra oltre il limite di rosa per un
ruolo (es. un quarto portiere): invece di bloccare lo scambio, il calciatore
in eccesso entra comunque in rosa ma resta marcato come "fuori rosa" finché
l'allenatore non libera uno slot per quel ruolo svincolando qualcuno (anche
l'acquisto appena fatto).

Revision ID: 2da9df541988
Revises: d6f2a9c1e385
Create Date: 2026-11-10 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2da9df541988"
down_revision: str | Sequence[str] | None = "d6f2a9c1e385"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fantasy_roster_slots",
        sa.Column(
            "exceeds_role_quota",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("fantasy_roster_slots", "exceeds_role_quota")
