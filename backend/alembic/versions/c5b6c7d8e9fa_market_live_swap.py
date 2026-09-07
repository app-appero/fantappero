"""Roster-full swap prompt for the live auction (EP08-09).

Revision ID: c5b6c7d8e9fa
Revises: c4a5b6d7e8f9
Create Date: 2026-09-04 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c5b6c7d8e9fa"
down_revision: str | Sequence[str] | None = "c4a5b6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "market_live_lot_swap_pending",
    "market_live_lot_swap_resolved",
    "market_live_lot_swap_declined",
)


def upgrade() -> None:
    op.execute("ALTER TYPE market_live_lot_status ADD VALUE IF NOT EXISTS 'pending_swap';")
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM league_audit_events
        WHERE action::text IN (
            'market_live_lot_swap_pending',
            'market_live_lot_swap_resolved',
            'market_live_lot_swap_declined'
        );
        """
    )
    # Postgres enum values cannot be dropped individually; left in place on downgrade
    # (same convention already used by other migrations in this codebase).
