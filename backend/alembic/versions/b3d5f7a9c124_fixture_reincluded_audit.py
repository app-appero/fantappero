"""Azione di audit per la reinclusione di una partita nel turno.

Revision ID: b3d5f7a9c124
Revises: a1c7e5b93d24
Create Date: 2026-11-17 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3d5f7a9c124"
down_revision: str | Sequence[str] | None = "a1c7e5b93d24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS 'fantasy_turn_fixture_reincluded';"
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM league_audit_events WHERE action::text = 'fantasy_turn_fixture_reincluded'"
        )
    )
