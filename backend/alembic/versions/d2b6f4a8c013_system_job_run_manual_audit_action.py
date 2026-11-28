"""Audit action per i job lanciati a mano dal pannello operatore (1.5).

«Esegui» e «Esegui tutti» (Job e Turni) lasciano una riga di audit di piattaforma
(``league_id`` nullo) con chi ha lanciato, quando e quale job.

Revision ID: d2b6f4a8c013
Revises: a4d7c2e9f610
Create Date: 2026-11-28 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d2b6f4a8c013"
down_revision: str | Sequence[str] | None = "a4d7c2e9f610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTION = "system_job_run_manual"


def upgrade() -> None:
    op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{_NEW_AUDIT_ACTION}';")


def downgrade() -> None:
    op.execute(f"DELETE FROM league_audit_events WHERE action::text = '{_NEW_AUDIT_ACTION}';")
    # I valori enum di Postgres non si possono rimuovere singolarmente: stessa
    # convenzione già usata dalle altre migration di questo codebase.
