"""Trade admin approval and per-team proposal limit (EP08-07 / FR-MKT-03).

Revision ID: a7c2e4b6d568
Revises: f6b9d1e3a457
Create Date: 2026-08-18 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7c2e4b6d568"
down_revision: str | Sequence[str] | None = "f6b9d1e3a457"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TRADE_STATUSES = ("pending_approval", "executed", "rejected_by_admin")
_NEW_AUDIT_ACTIONS = ("market_trade_approved", "market_trade_rejected_by_admin")


def upgrade() -> None:
    for value in _NEW_TRADE_STATUSES:
        op.execute(f"ALTER TYPE trade_status ADD VALUE IF NOT EXISTS '{value}';")
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    op.add_column(
        "league_rules",
        sa.Column(
            "require_trade_approval",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "league_rules",
        sa.Column(
            "max_active_trade_proposals_per_team",
            sa.Integer(),
            server_default=sa.text("10"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_league_rules_max_active_trade_proposals_per_team"),
        "league_rules",
        "max_active_trade_proposals_per_team >= 1",
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM league_audit_events
        WHERE action::text IN ({", ".join(f"'{action}'" for action in _NEW_AUDIT_ACTIONS)});
        """
    )
    op.drop_constraint(
        op.f("ck_league_rules_max_active_trade_proposals_per_team"),
        "league_rules",
        type_="check",
    )
    op.drop_column("league_rules", "max_active_trade_proposals_per_team")
    op.drop_column("league_rules", "require_trade_approval")
    # Postgres enum values cannot be dropped individually; left in place on downgrade
    # (same convention already used by other migrations in this codebase).
