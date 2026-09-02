"""Audit actions for operator promote/revoke (EP11-04).

Revision ID: a123d0e725fc
Revises: 3eae5a327551
Create Date: 2026-08-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a123d0e725fc"
down_revision: str | Sequence[str] | None = "3eae5a327551"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = ("platform_operator_promoted", "platform_operator_revoked")


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM league_audit_events
        WHERE action::text IN ({", ".join(f"'{action}'" for action in _NEW_AUDIT_ACTIONS)});
        """
    )
    # Postgres enum values cannot be dropped individually; left in place on downgrade
    # (same convention already used by other migrations in this codebase).
