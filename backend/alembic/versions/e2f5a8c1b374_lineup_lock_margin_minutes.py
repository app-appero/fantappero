"""Margine di preavviso del lock per-giocatore (EP-turni-automazione).

Minuti prima del kickoff reale del singolo giocatore oltre cui si blocca in
formazione. Il lock resta per atleta (formazione a step invariata): il
margine anticipa solo l'istante in cui scatta. Additiva: le leghe esistenti
ereditano il default 15.

Revision ID: e2f5a8c1b374
Revises: d8e3b5f7c962
Create Date: 2026-08-31 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2f5a8c1b374"
down_revision: str | Sequence[str] | None = "d8e3b5f7c962"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEAGUE_RULES = "league_rules"
_COLUMN = "lineup_lock_margin_minutes"
_CHECK = "ck_league_rules_lineup_lock_margin_minutes"


def upgrade() -> None:
    op.add_column(
        _LEAGUE_RULES,
        sa.Column(
            _COLUMN,
            sa.Integer(),
            nullable=False,
            server_default=sa.text("15"),
        ),
    )
    op.create_check_constraint(
        _CHECK,
        _LEAGUE_RULES,
        f"{_COLUMN} BETWEEN 0 AND 60",
    )


def downgrade() -> None:
    op.drop_constraint(_CHECK, _LEAGUE_RULES, type_="check")
    op.drop_column(_LEAGUE_RULES, _COLUMN)
