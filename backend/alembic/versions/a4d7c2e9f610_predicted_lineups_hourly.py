"""Formazioni probabili: il job passa da ogni 24 ore a ogni ora.

Il giro a ora fissa (crontab 07:00 UTC) non partiva: lo scheduler del pannello
riscrive ogni voce come intervallo con la frequenza salvata in ``system_jobs``.
Ora il job controlla ogni ora e scarica solo le partite senza dati dal mattino.
La riga esistente con il vecchio default (86400) passa a 3600; una frequenza
scelta a mano dall'operatore resta com'è.

Revision ID: a4d7c2e9f610
Revises: c3e8a5f17b24
Create Date: 2026-11-28 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4d7c2e9f610"
down_revision: str | Sequence[str] | None = "c3e8a5f17b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KEY = "sports-predicted-lineups"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE system_jobs SET interval_seconds = 3600 "
            "WHERE key = :key AND interval_seconds = 86400"
        ).bindparams(key=_KEY)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE system_jobs SET interval_seconds = 86400 "
            "WHERE key = :key AND interval_seconds = 3600"
        ).bindparams(key=_KEY)
    )
