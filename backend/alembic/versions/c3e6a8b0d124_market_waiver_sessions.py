"""Waiver market window: release-on-win bids (EP08-03 / FR-MKT-01).

Revision ID: c3e6a8b0d124
Revises: b2d4f6a8c013
Create Date: 2026-08-18 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3e6a8b0d124"
down_revision: str | Sequence[str] | None = "b2d4f6a8c013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE market_session_kind ADD VALUE IF NOT EXISTS 'waiver';")
    op.execute(
        "ALTER TYPE credit_ledger_reason ADD VALUE IF NOT EXISTS 'market_waiver_acquisition';"
    )

    op.add_column(
        "market_bids",
        sa.Column("release_athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_market_bids_release_athlete_id_athletes"),
        "market_bids",
        "athletes",
        ["release_athlete_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_market_bids_release_athlete_id_athletes"),
        "market_bids",
        type_="foreignkey",
    )
    op.drop_column("market_bids", "release_athlete_id")
    # Postgres enum values cannot be dropped individually; left in place on downgrade
    # (same convention already used by other migrations in this codebase).
