"""Provenienza della formazione sintetizzata dal motore di calcolo turno (EP-turni-calcolo).

Aggiunge `lineup_submissions.auto_resolution_source` (NULL = submission
normale, umana o IA) e il nuovo evento di audit
`fantasy_lineup_auto_resolved`, usati da
`fantasy_lineups/fallback_service.py::ensure_lineup_submissions_for_round`
quando una squadra non ha una formazione propria alla chiusura del turno.

Revision ID: b4d8e19a5f36
Revises: e2f5a8c1b374
Create Date: 2026-09-01 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4d8e19a5f36"
down_revision: str | Sequence[str] | None = "e2f5a8c1b374"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

lineup_auto_resolution_source = postgresql.ENUM(
    "draft",
    "previous_round",
    "zero_fallback",
    name="lineup_auto_resolution_source",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS 'fantasy_lineup_auto_resolved';"
    )

    lineup_auto_resolution_source.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "lineup_submissions",
        sa.Column("auto_resolution_source", lineup_auto_resolution_source, nullable=True),
    )


def downgrade() -> None:
    # Stessa convenzione delle altre aggiunte a league_audit_action in questo
    # progetto (es. f2b6d9c1a847): cancella le righe che usano il valore
    # aggiunto qui prima che una downgrade precedente ricostruisca il tipo
    # enum alla sua istantanea storica.
    op.execute(
        "DELETE FROM league_audit_events WHERE action::text = 'fantasy_lineup_auto_resolved'"
    )
    op.drop_column("lineup_submissions", "auto_resolution_source")
    lineup_auto_resolution_source.drop(op.get_bind(), checkfirst=True)
