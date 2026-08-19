"""League rules standard preset and regulation update audit (EP03-02).

Revision ID: f1a7d4c6e809
Revises: e0f6a3b4c507
Create Date: 2026-07-31 11:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f1a7d4c6e809"
down_revision: str | Sequence[str] | None = "e0f6a3b4c507"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'league_audit_action'
                  AND e.enumlabel = 'league_rules_updated'
            ) THEN
                ALTER TYPE league_audit_action ADD VALUE 'league_rules_updated';
            END IF;
        END$$;
        """
    )

    op.create_table(
        "league_rules",
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
        sa.Column("preset_name", sa.String(length=32), nullable=False, server_default="standard"),
        sa.Column("participant_count", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("roster_size", sa.Integer(), nullable=False, server_default="35"),
        sa.Column("goalkeepers", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("defenders", sa.Integer(), nullable=False, server_default="11"),
        sa.Column("midfielders", sa.Integer(), nullable=False, server_default="11"),
        sa.Column("forwards", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("total_credits", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("allow_trades", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_manual_invites", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.CheckConstraint("participant_count BETWEEN 4 AND 10", name=op.f("ck_league_rules_participant_range")),
        sa.CheckConstraint("roster_size = 35", name=op.f("ck_league_rules_roster_size")),
        sa.CheckConstraint("goalkeepers = 3", name=op.f("ck_league_rules_goalkeepers")),
        sa.CheckConstraint("defenders = 11", name=op.f("ck_league_rules_defenders")),
        sa.CheckConstraint("midfielders = 11", name=op.f("ck_league_rules_midfielders")),
        sa.CheckConstraint("forwards = 10", name=op.f("ck_league_rules_forwards")),
        sa.CheckConstraint(
            "goalkeepers + defenders + midfielders + forwards = roster_size",
            name=op.f("ck_league_rules_roster_sum"),
        ),
        sa.CheckConstraint("total_credits > 0", name=op.f("ck_league_rules_total_credits")),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_league_rules_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_league_rules")),
        sa.UniqueConstraint("league_id", name=op.f("uq_league_rules_league_id")),
    )
    op.create_index(op.f("ix_league_rules_league_id"), "league_rules", ["league_id"], unique=True)

    op.execute(
        """
        INSERT INTO league_rules (
            league_id,
            preset_name,
            participant_count,
            roster_size,
            goalkeepers,
            defenders,
            midfielders,
            forwards,
            total_credits,
            allow_trades,
            allow_manual_invites
        )
        SELECT
            id,
            'standard',
            8,
            35,
            3,
            11,
            11,
            10,
            1000,
            true,
            true
        FROM leagues
        ON CONFLICT (league_id) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM league_audit_events WHERE action = 'league_rules_updated';")
    op.drop_index(op.f("ix_league_rules_league_id"), table_name="league_rules")
    op.drop_table("league_rules")

    op.execute("ALTER TYPE league_audit_action RENAME TO league_audit_action_old;")
    op.execute("CREATE TYPE league_audit_action AS ENUM ('league_created');")
    op.execute(
        """
        ALTER TABLE league_audit_events
        ALTER COLUMN action
        TYPE league_audit_action
        USING action::text::league_audit_action;
        """
    )
    op.execute("DROP TYPE league_audit_action_old;")

