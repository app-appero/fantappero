"""Credit accounts and immutable ledger entries (EP05-02).

Revision ID: c5e8f2a4b031
Revises: b8d4f1a2c019
Create Date: 2026-08-10 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e8f2a4b031"
down_revision: str | Sequence[str] | None = "b8d4f1a2c019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "credit_account_initialized",
    "credit_ledger_entry_posted",
)

credit_ledger_reason = postgresql.ENUM(
    "initial_allocation",
    "admin_adjustment",
    name="credit_ledger_reason",
    create_type=False,
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    credit_ledger_reason.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "credit_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
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
        sa.Column("fantasy_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("balance", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("balance >= 0", name=op.f("ck_credit_accounts_balance")),
        sa.CheckConstraint("version >= 0", name=op.f("ck_credit_accounts_version")),
        sa.ForeignKeyConstraint(
            ["fantasy_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_credit_accounts_fantasy_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_accounts")),
        sa.UniqueConstraint("fantasy_team_id", name=op.f("uq_credit_accounts_fantasy_team_id")),
    )

    op.create_table(
        "credit_ledger_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column(
            "reason",
            credit_ledger_reason,
            nullable=False,
        ),
        sa.Column("transaction_id", sa.String(length=128), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["credit_accounts.id"],
            name=op.f("fk_credit_ledger_entries_account_id_credit_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_credit_ledger_entries_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_ledger_entries")),
        sa.UniqueConstraint(
            "account_id",
            "transaction_id",
            name=op.f("uq_credit_ledger_entries_account_transaction"),
        ),
    )
    op.create_index(
        "ix_credit_ledger_entries_account_id",
        "credit_ledger_entries",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_credit_ledger_entries_created_at",
        "credit_ledger_entries",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_credit_ledger_entries_actor_id"),
        "credit_ledger_entries",
        ["actor_id"],
        unique=False,
    )

    # Backfill existing fantasy teams: reconstructable initial allocation.
    op.execute(
        """
        INSERT INTO credit_accounts (id, fantasy_team_id, balance, version)
        SELECT
            gen_random_uuid(),
            ft.id,
            COALESCE(lr.total_credits, 1000),
            1
        FROM fantasy_teams ft
        LEFT JOIN league_rules lr ON lr.league_id = ft.league_id
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_accounts ca WHERE ca.fantasy_team_id = ft.id
        );
        """
    )
    op.execute(
        """
        INSERT INTO credit_ledger_entries (
            id, account_id, amount, reason, transaction_id, balance_after, note
        )
        SELECT
            gen_random_uuid(),
            ca.id,
            ca.balance,
            'initial_allocation'::credit_ledger_reason,
            'initial:' || ca.fantasy_team_id::text,
            ca.balance,
            'Allocazione iniziale (migrazione EP05-02)'
        FROM credit_accounts ca
        WHERE NOT EXISTS (
            SELECT 1 FROM credit_ledger_entries e WHERE e.account_id = ca.id
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM league_audit_events
        WHERE action::text IN (
            'credit_account_initialized',
            'credit_ledger_entry_posted'
        );
        """
    )
    op.drop_index(op.f("ix_credit_ledger_entries_actor_id"), table_name="credit_ledger_entries")
    op.drop_index("ix_credit_ledger_entries_created_at", table_name="credit_ledger_entries")
    op.drop_index("ix_credit_ledger_entries_account_id", table_name="credit_ledger_entries")
    op.drop_table("credit_ledger_entries")
    op.drop_table("credit_accounts")
    op.execute("DROP TYPE IF EXISTS credit_ledger_reason;")
