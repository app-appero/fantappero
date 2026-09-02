"""Fantapunti aggregati in classifica (EP13-P02).

Additiva e retrocompatibile: aggiunge due colonne con default 0 su
``league_standings``. Nessun dato esistente viene cancellato o riscritto dalla
migrazione; i valori reali compaiono al primo ricalcolo della classifica, che
per costruzione riparte sempre dagli slot di calendario (FR-CLS-01).

Revision ID: b4d7e2f9c118
Revises: a123d0e725fc
Create Date: 2026-08-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4d7e2f9c118"
down_revision: str | Sequence[str] | None = "a123d0e725fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "league_standings"
_COLUMNS = ("fantasy_points_for", "fantasy_points_against")


def upgrade() -> None:
    for column in _COLUMNS:
        op.add_column(
            _TABLE,
            sa.Column(
                column,
                sa.Float(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    for column in _COLUMNS:
        op.drop_column(_TABLE, column)
