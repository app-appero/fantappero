"""Expiring and revocable league invitations (EP03-03).

Revision ID: a2b8e5d7f910
Revises: f1a7d4c6e809
Create Date: 2026-08-03 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a2b8e5d7f910"
down_revision: str | Sequence[str] | None = "f1a7d4c6e809"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
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

    op.create_table(
        "league_invites",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("league_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_league_invites_created_by_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_league_invites_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_league_invites")),
    )
    op.create_index("ix_league_invites_league_id", "league_invites", ["league_id"])
    op.create_index("ix_league_invites_created_by_id", "league_invites", ["created_by_id"])
    op.create_index(
        "ix_league_invites_token_hash",
        "league_invites",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_league_invites_code_hash",
        "league_invites",
        ["code_hash"],
        unique=True,
    )
    op.create_index(
        "ix_league_invites_active",
        "league_invites",
        ["league_id", "revoked_at", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_league_invites_active", table_name="league_invites")
    op.drop_index("ix_league_invites_code_hash", table_name="league_invites")
    op.drop_index("ix_league_invites_token_hash", table_name="league_invites")
    op.drop_index("ix_league_invites_created_by_id", table_name="league_invites")
    op.drop_index("ix_league_invites_league_id", table_name="league_invites")
    op.drop_table("league_invites")

    actions = "', '".join(_NEW_AUDIT_ACTIONS)
    op.execute(f"DELETE FROM league_audit_events WHERE action::text IN ('{actions}');")
    op.execute("ALTER TYPE league_audit_action RENAME TO league_audit_action_old;")
    op.execute(
        "CREATE TYPE league_audit_action AS ENUM ('league_created', 'league_rules_updated');"
    )
    op.execute(
        """
        ALTER TABLE league_audit_events
        ALTER COLUMN action
        TYPE league_audit_action
        USING action::text::league_audit_action;
        """
    )
    op.execute("DROP TYPE league_audit_action_old;")
