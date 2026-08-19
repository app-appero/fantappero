"""Audit action for league listone refresh from provider.

Revision ID: c9d2e5f8a014
Revises: a8c1d4e7f013
Create Date: 2026-08-05 06:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c9d2e5f8a014"
down_revision: str | Sequence[str] | None = "a8c1d4e7f013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PREVIOUS_AUDIT_ACTIONS = (
    "league_created",
    "league_rules_updated",
    "league_invite_created",
    "league_invite_revoked",
    "league_member_joined",
    "league_member_removed",
    "league_admin_transferred",
    "league_state_changed",
    "named_invite_created",
    "named_invite_accepted",
    "named_invite_declined",
    "named_invite_revoked",
    "league_calendar_generated",
    "league_calendar_confirmed",
    "league_role_override_set",
    "league_role_override_cleared",
)


def upgrade() -> None:
    op.execute(
        "ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS 'league_listone_refreshed';"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM league_audit_events WHERE action::text = 'league_listone_refreshed';"
    )
    op.execute("ALTER TYPE league_audit_action RENAME TO league_audit_action_old;")
    previous_actions = "', '".join(_PREVIOUS_AUDIT_ACTIONS)
    op.execute(f"CREATE TYPE league_audit_action AS ENUM ('{previous_actions}');")
    op.execute(
        """
        ALTER TABLE league_audit_events
        ALTER COLUMN action TYPE league_audit_action
        USING action::text::league_audit_action;
        """
    )
    op.execute("DROP TYPE league_audit_action_old;")
