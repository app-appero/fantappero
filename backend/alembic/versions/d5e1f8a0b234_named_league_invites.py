"""Fantasy coach directory and named invitations.

Revision ID: d5e1f8a0b234
Revises: c4d0e7f9a123
Create Date: 2026-08-04 07:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5e1f8a0b234"
down_revision: str | Sequence[str] | None = "c4d0e7f9a123"
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
)
_NEW_AUDIT_ACTIONS = (
    "named_invite_created",
    "named_invite_accepted",
    "named_invite_declined",
    "named_invite_revoked",
)


def upgrade() -> None:
    user_type = postgresql.ENUM("human", "ai", name="user_type", create_type=False)
    user_type.create(op.get_bind(), checkfirst=True)
    named_status = postgresql.ENUM(
        "pending",
        "accepted",
        "declined",
        "revoked",
        "expired",
        name="named_invite_status",
        create_type=False,
    )
    named_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "users",
        sa.Column(
            "user_type",
            user_type,
            nullable=False,
            server_default=sa.text("'human'::user_type"),
        ),
    )
    op.add_column(
        "user_profiles",
        sa.Column(
            "available_for_invites",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_table(
        "named_league_invites",
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            named_status,
            nullable=False,
            server_default=sa.text("'pending'::named_invite_status"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "recipient_id <> created_by_id",
            name="ck_named_league_invites_recipient_not_creator",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_named_league_invites_expiry_after_creation",
        ),
        sa.CheckConstraint(
            "(status IN ('accepted', 'declined')) = (responded_at IS NOT NULL)",
            name="ck_named_league_invites_response_timestamp",
        ),
        sa.CheckConstraint(
            "(status = 'revoked') = (revoked_at IS NOT NULL)",
            name="ck_named_league_invites_revocation_timestamp",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_named_league_invites_pending_recipient",
        "named_league_invites",
        ["league_id", "recipient_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_named_league_invites_recipient_status",
        "named_league_invites",
        ["recipient_id", "status", "expires_at"],
    )
    op.create_index(
        "ix_named_league_invites_league_status",
        "named_league_invites",
        ["league_id", "status"],
    )

    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    # AI accounts must always remain available for named invites.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fantappero_enforce_ai_invite_availability()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_TABLE_NAME = 'user_profiles' THEN
            IF EXISTS (
              SELECT 1
              FROM users
              WHERE users.id = NEW.user_id
                AND users.user_type = 'ai'
                AND NEW.available_for_invites IS DISTINCT FROM TRUE
            ) THEN
              RAISE EXCEPTION 'AI users must remain available for invites';
            END IF;
            RETURN NEW;
          END IF;

          IF NEW.user_type = 'ai' THEN
            UPDATE user_profiles
            SET available_for_invites = TRUE
            WHERE user_id = NEW.id
              AND available_for_invites IS DISTINCT FROM TRUE;
          END IF;
          RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_user_profiles_ai_invite_availability
        BEFORE INSERT OR UPDATE OF available_for_invites ON user_profiles
        FOR EACH ROW
        EXECUTE FUNCTION fantappero_enforce_ai_invite_availability();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_ai_invite_availability
        AFTER INSERT OR UPDATE OF user_type ON users
        FOR EACH ROW
        WHEN (NEW.user_type = 'ai')
        EXECUTE FUNCTION fantappero_enforce_ai_invite_availability();
        """
    )


def downgrade() -> None:
    # Lossy: removes named invites, related audit rows, user type, and availability.
    op.execute("DROP TRIGGER IF EXISTS trg_users_ai_invite_availability ON users;")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_user_profiles_ai_invite_availability ON user_profiles;"
    )
    op.execute("DROP FUNCTION IF EXISTS fantappero_enforce_ai_invite_availability();")
    op.drop_table("named_league_invites")
    op.drop_column("user_profiles", "available_for_invites")
    op.drop_column("users", "user_type")
    op.execute("DROP TYPE named_invite_status;")
    op.execute("DROP TYPE user_type;")

    new_actions = "', '".join(_NEW_AUDIT_ACTIONS)
    op.execute(
        f"DELETE FROM league_audit_events WHERE action::text IN ('{new_actions}');"
    )
    op.execute("ALTER TYPE league_audit_action RENAME TO league_audit_action_old;")
    actions = "', '".join(_PREVIOUS_AUDIT_ACTIONS)
    op.execute(f"CREATE TYPE league_audit_action AS ENUM ('{actions}');")
    op.execute(
        """
        ALTER TABLE league_audit_events
        ALTER COLUMN action TYPE league_audit_action
        USING action::text::league_audit_action;
        """
    )
    op.execute("DROP TYPE league_audit_action_old;")
