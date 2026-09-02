"""Auction resolution: winners, tiebreak sessions, market audit reason (EP08-02).

Revision ID: b2d4f6a8c013
Revises: a1c3e5f7b902
Create Date: 2026-08-18 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2d4f6a8c013"
down_revision: str | Sequence[str] | None = "a1c3e5f7b902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "market_session_resolved",
    "market_tiebreak_opened",
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")
    op.execute("ALTER TYPE credit_ledger_reason ADD VALUE IF NOT EXISTS 'market_auction_win';")
    op.execute("ALTER TYPE roster_ownership_source ADD VALUE IF NOT EXISTS 'market';")

    op.add_column(
        "market_sessions",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "market_sessions",
        sa.Column("parent_session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "market_sessions",
        sa.Column("target_athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "market_sessions",
        sa.Column("eligible_team_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_market_sessions_parent_session_id_market_sessions"),
        "market_sessions",
        "market_sessions",
        ["parent_session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_market_sessions_target_athlete_id_athletes"),
        "market_sessions",
        "athletes",
        ["target_athlete_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_market_sessions_parent_session_id",
        "market_sessions",
        ["parent_session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM league_audit_events
        WHERE action::text IN ('market_session_resolved', 'market_tiebreak_opened');
        """
    )
    op.drop_index("ix_market_sessions_parent_session_id", table_name="market_sessions")
    op.drop_constraint(
        op.f("fk_market_sessions_target_athlete_id_athletes"),
        "market_sessions",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_market_sessions_parent_session_id_market_sessions"),
        "market_sessions",
        type_="foreignkey",
    )
    op.drop_column("market_sessions", "eligible_team_ids")
    op.drop_column("market_sessions", "target_athlete_id")
    op.drop_column("market_sessions", "parent_session_id")
    op.drop_column("market_sessions", "resolved_at")
    # Postgres enum values cannot be dropped individually; left in place on downgrade
    # (same convention already used by other migrations in this codebase).
