"""Admin review tracking for transfers pending manual check (OQ-12).

Revision ID: 37c365bf2399
Revises: 2fb4800de433
Create Date: 2026-09-25 01:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "37c365bf2399"
down_revision: str | Sequence[str] | None = "2fb4800de433"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transfers",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "transfers",
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_transfers_reviewed_by_user_id_users"),
        "transfers",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_transfers_requires_admin_review"),
        "transfers",
        ["requires_admin_review"],
        unique=False,
    )
    op.execute(
        "ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS 'roster_transfer_reviewed';"
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_transfers_requires_admin_review"),
        table_name="transfers",
    )
    op.drop_constraint(
        op.f("fk_transfers_reviewed_by_user_id_users"),
        "transfers",
        type_="foreignkey",
    )
    op.drop_column("transfers", "reviewed_by_user_id")
    op.drop_column("transfers", "reviewed_at")
