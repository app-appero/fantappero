"""Soglia di copertura formazione per la validità di un turno (EP-turni-copertura).

Un Turno Europeo è valido solo se ogni fantallenatore può schierare almeno
questa frazione degli 11 titolari con i giocatori della propria rosa il cui
club reale gioca in quella finestra. Additiva: le leghe esistenti ereditano
il default 0.75.

Revision ID: d8e3b5f7c962
Revises: c7f2a4d6e831
Create Date: 2026-08-30 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8e3b5f7c962"
down_revision: str | Sequence[str] | None = "c7f2a4d6e831"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEAGUE_RULES = "league_rules"
_COLUMN = "turn_coverage_threshold"
_CHECK = "ck_league_rules_turn_coverage_threshold"


def upgrade() -> None:
    op.add_column(
        _LEAGUE_RULES,
        sa.Column(
            _COLUMN,
            sa.Numeric(precision=3, scale=2),
            nullable=False,
            server_default=sa.text("0.75"),
        ),
    )
    op.create_check_constraint(
        _CHECK,
        _LEAGUE_RULES,
        f"{_COLUMN} BETWEEN 0.50 AND 1.00",
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK, _LEAGUE_RULES, type_="check")
    op.drop_column(_LEAGUE_RULES, _COLUMN)
