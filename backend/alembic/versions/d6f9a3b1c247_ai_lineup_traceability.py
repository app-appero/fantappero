"""Tracciabilità della formazione automatica IA (EP13-P05 / ADR-0005).

Additiva e retrocompatibile:

* ``official_lineups.fetched_at`` — istante di acquisizione dal provider,
  distinto da ``updated_at`` che cambia a ogni ri-sincronizzazione. Senza
  questo campo non si potrebbe dimostrare che una formazione automatica non
  ha usato dati arrivati dopo il lock.
* ``lineup_submissions`` — flag ``system_generated_ai``, versione algoritmo,
  istante di decisione e log delle decisioni per candidato.

Nessun dato viene cancellato. Le formazioni esistenti restano valide con
``system_generated_ai = false``, che è la verità: sono state schierate da
persone.

Revision ID: d6f9a3b1c247
Revises: c5e8a1f3d229
Create Date: 2026-08-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d6f9a3b1c247"
down_revision: str | Sequence[str] | None = "c5e8a1f3d229"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LINEUPS = "official_lineups"
_SUBMISSIONS = "lineup_submissions"


def upgrade() -> None:
    op.add_column(
        _LINEUPS,
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Le distinte già acquisite non hanno una provenienza dimostrabile:
    # restano NULL e il segnale di titolarità non le userà (ADR-0005 §4).

    op.add_column(
        _SUBMISSIONS,
        sa.Column(
            "system_generated_ai",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        _SUBMISSIONS,
        sa.Column("ai_algorithm_version", sa.String(length=32), nullable=True),
    )
    op.add_column(
        _SUBMISSIONS,
        sa.Column("ai_decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        _SUBMISSIONS,
        sa.Column("ai_decision_log", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column(_SUBMISSIONS, "ai_decision_log")
    op.drop_column(_SUBMISSIONS, "ai_decided_at")
    op.drop_column(_SUBMISSIONS, "ai_algorithm_version")
    op.drop_column(_SUBMISSIONS, "system_generated_ai")
    op.drop_column(_LINEUPS, "fetched_at")
