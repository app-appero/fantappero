"""Configurable release refund percentages and ledger reason (EP08-04 / FR-MKT-02).

Revision ID: d4f7b9c1e235
Revises: c3e6a8b0d124
Create Date: 2026-08-18 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f7b9c1e235"
down_revision: str | Sequence[str] | None = "c3e6a8b0d124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE credit_ledger_reason ADD VALUE IF NOT EXISTS 'market_release_refund';"
    )

    op.add_column(
        "league_rules",
        sa.Column(
            "voluntary_release_refund_percent",
            sa.Integer(),
            server_default=sa.text("50"),
            nullable=False,
        ),
    )
    op.add_column(
        "league_rules",
        sa.Column(
            "league_exit_refund_percent",
            sa.Integer(),
            server_default=sa.text("100"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_league_rules_voluntary_release_refund_percent"),
        "league_rules",
        "voluntary_release_refund_percent BETWEEN 0 AND 100",
    )
    op.create_check_constraint(
        op.f("ck_league_rules_league_exit_refund_percent"),
        "league_rules",
        "league_exit_refund_percent BETWEEN 0 AND 100",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_league_rules_league_exit_refund_percent"), "league_rules", type_="check"
    )
    op.drop_constraint(
        op.f("ck_league_rules_voluntary_release_refund_percent"), "league_rules", type_="check"
    )
    op.drop_column("league_rules", "league_exit_refund_percent")
    op.drop_column("league_rules", "voluntary_release_refund_percent")
    # Postgres enum values cannot be dropped individually; left in place on downgrade
    # (same convention already used by other migrations in this codebase).
