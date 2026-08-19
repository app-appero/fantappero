"""League lifecycle states and transition audit details (EP03-05).

Revision ID: c4d0e7f9a123
Revises: b3c9f6e8a012
Create Date: 2026-08-03 13:50:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d0e7f9a123"
down_revision: str | Sequence[str] | None = "b3c9f6e8a012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PREVIOUS_STATES = ("draft", "active")
_PREVIOUS_AUDIT_ACTIONS = (
    "league_created",
    "league_rules_updated",
    "league_invite_created",
    "league_invite_revoked",
    "league_member_joined",
    "league_member_removed",
    "league_admin_transferred",
)


def upgrade() -> None:
    op.execute("ALTER TYPE league_state ADD VALUE IF NOT EXISTS 'configuring' AFTER 'draft';")
    op.execute("ALTER TYPE league_state ADD VALUE IF NOT EXISTS 'auction' AFTER 'configuring';")
    op.execute("ALTER TYPE league_state ADD VALUE IF NOT EXISTS 'concluded' AFTER 'active';")
    op.execute("ALTER TYPE league_state ADD VALUE IF NOT EXISTS 'archived' AFTER 'concluded';")
    op.execute(
        "ALTER TYPE league_audit_action "
        "ADD VALUE IF NOT EXISTS 'league_state_changed' AFTER 'league_admin_transferred';"
    )
    op.add_column(
        "league_audit_events",
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    # Lossy compatibility mapping to the pre-EP03-05 lifecycle:
    # states before season start become draft; started/final states become active.
    op.execute(
        "UPDATE leagues SET state = 'draft' WHERE state::text IN ('configuring', 'auction');"
    )
    op.execute(
        "UPDATE leagues SET state = 'active' WHERE state::text IN ('concluded', 'archived');"
    )
    op.execute("DELETE FROM league_audit_events WHERE action::text = 'league_state_changed';")

    op.execute("ALTER TYPE league_state RENAME TO league_state_old;")
    previous_states = "', '".join(_PREVIOUS_STATES)
    op.execute(f"CREATE TYPE league_state AS ENUM ('{previous_states}');")
    op.execute(
        """
        ALTER TABLE leagues
        ALTER COLUMN state DROP DEFAULT,
        ALTER COLUMN state TYPE league_state USING state::text::league_state,
        ALTER COLUMN state SET DEFAULT 'draft'::league_state;
        """
    )
    op.execute("DROP TYPE league_state_old;")

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
    op.drop_column("league_audit_events", "details")
