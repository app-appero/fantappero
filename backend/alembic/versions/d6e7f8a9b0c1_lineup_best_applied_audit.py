"""Audit action for self-service "apply best lineup" (EP-self-service).

Revision ID: d6e7f8a9b0c1
Revises: c5b6c7d8e9fa
Create Date: 2026-09-05 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | Sequence[str] | None = "c5b6c7d8e9fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS 'fantasy_lineup_best_applied';")


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM league_audit_events WHERE action::text = 'fantasy_lineup_best_applied'"
        )
    )
