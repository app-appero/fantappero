"""Allow league delete audit rows to survive hard-delete (EP03-05-EXT).

Revision ID: a7c3e9f1b018
Revises: f3a9c1d0e017
Create Date: 2026-08-05 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a7c3e9f1b018"
down_revision: str | Sequence[str] | None = "f3a9c1d0e017"
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
    "league_listone_refreshed",
)


def upgrade() -> None:
    op.execute(
        "ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS 'league_deleted';"
    )
    op.drop_constraint(
        op.f("fk_league_audit_events_league_id_leagues"),
        "league_audit_events",
        type_="foreignkey",
    )
    op.alter_column("league_audit_events", "league_id", nullable=True)
    op.create_foreign_key(
        op.f("fk_league_audit_events_league_id_leagues"),
        "league_audit_events",
        "leagues",
        ["league_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.execute("DELETE FROM league_audit_events WHERE action::text = 'league_deleted';")
    op.execute("DELETE FROM league_audit_events WHERE league_id IS NULL")
    op.drop_constraint(
        op.f("fk_league_audit_events_league_id_leagues"),
        "league_audit_events",
        type_="foreignkey",
    )
    op.alter_column("league_audit_events", "league_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_league_audit_events_league_id_leagues"),
        "league_audit_events",
        "leagues",
        ["league_id"],
        ["id"],
        ondelete="CASCADE",
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
