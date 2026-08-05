"""Audit actions for league member management (EP03-04).

Revision ID: b3c9f6e8a012
Revises: a2b8e5d7f910
Create Date: 2026-08-03 12:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b3c9f6e8a012"
down_revision: str | Sequence[str] | None = "a2b8e5d7f910"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "league_member_removed",
    "league_admin_transferred",
)

_PREVIOUS_AUDIT_ACTIONS = (
    "league_created",
    "league_rules_updated",
    "league_invite_created",
    "league_invite_revoked",
    "league_member_joined",
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    WHERE t.typname = 'league_audit_action'
                      AND e.enumlabel = '{action}'
                ) THEN
                    ALTER TYPE league_audit_action ADD VALUE '{action}';
                END IF;
            END$$;
            """
        )


def downgrade() -> None:
    actions = "', '".join(_NEW_AUDIT_ACTIONS)
    previous_actions = "', '".join(_PREVIOUS_AUDIT_ACTIONS)
    op.execute(f"DELETE FROM league_audit_events WHERE action::text IN ('{actions}');")
    op.execute("ALTER TYPE league_audit_action RENAME TO league_audit_action_old;")
    op.execute(f"CREATE TYPE league_audit_action AS ENUM ('{previous_actions}');")
    op.execute(
        """
        ALTER TABLE league_audit_events
        ALTER COLUMN action
        TYPE league_audit_action
        USING action::text::league_audit_action;
        """
    )
    op.execute("DROP TYPE league_audit_action_old;")
