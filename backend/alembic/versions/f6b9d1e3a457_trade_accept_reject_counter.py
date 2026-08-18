"""Trade accept/reject/counter transitions and execution (EP08-06 / FR-MKT-03).

Revision ID: f6b9d1e3a457
Revises: e5a8c0d2f346
Create Date: 2026-08-18 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f6b9d1e3a457"
down_revision: str | Sequence[str] | None = "e5a8c0d2f346"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TRADE_STATUSES = ("accepted", "rejected", "countered")
_NEW_LEDGER_REASONS = ("market_trade_credits_sent", "market_trade_credits_received")
_NEW_AUDIT_ACTIONS = (
    "market_trade_accepted",
    "market_trade_rejected",
    "market_trade_countered",
)


def upgrade() -> None:
    for value in _NEW_TRADE_STATUSES:
        op.execute(f"ALTER TYPE trade_status ADD VALUE IF NOT EXISTS '{value}';")
    for value in _NEW_LEDGER_REASONS:
        op.execute(f"ALTER TYPE credit_ledger_reason ADD VALUE IF NOT EXISTS '{value}';")
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    op.add_column(
        "trade_proposals",
        sa.Column("counter_of_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "trade_proposals",
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_trade_proposals_counter_of_id_trade_proposals"),
        "trade_proposals",
        "trade_proposals",
        ["counter_of_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_trade_proposals_counter_of_id", "trade_proposals", ["counter_of_id"], unique=False
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM league_audit_events
        WHERE action::text IN (
            'market_trade_accepted', 'market_trade_rejected', 'market_trade_countered'
        );
        """
    )
    op.drop_index("ix_trade_proposals_counter_of_id", table_name="trade_proposals")
    op.drop_constraint(
        op.f("fk_trade_proposals_counter_of_id_trade_proposals"),
        "trade_proposals",
        type_="foreignkey",
    )
    op.drop_column("trade_proposals", "decided_at")
    op.drop_column("trade_proposals", "counter_of_id")
    # Postgres enum values cannot be dropped individually; left in place on downgrade
    # (same convention already used by other migrations in this codebase).
