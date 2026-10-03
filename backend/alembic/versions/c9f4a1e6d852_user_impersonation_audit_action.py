"""Audit action for operator impersonation (support tool).

Revision ID: c9f4a1e6d852
Revises: b6f1c8e3a729
Create Date: 2026-10-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c9f4a1e6d852"
down_revision: str | Sequence[str] | None = "b6f1c8e3a729"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTION = "user_impersonation_started"


def upgrade() -> None:
    op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{_NEW_AUDIT_ACTION}';")


def downgrade() -> None:
    op.execute(
        f"DELETE FROM league_audit_events WHERE action::text = '{_NEW_AUDIT_ACTION}';"
    )
    # I valori enum di Postgres non si possono rimuovere singolarmente: stessa
    # convenzione già usata dalle altre migration di questo codebase.
