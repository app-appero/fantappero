"""Roster slot purchase credits and related ledger reasons (EP05-03).

Revision ID: d6a9c2e4f032
Revises: c5e8f2a4b031
Create Date: 2026-08-11 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6a9c2e4f032"
down_revision: str | Sequence[str] | None = "c5e8f2a4b031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_LEDGER_REASONS = (
    "roster_purchase",
    "roster_release_refund",
)


def upgrade() -> None:
    for reason in _NEW_LEDGER_REASONS:
        op.execute(f"ALTER TYPE credit_ledger_reason ADD VALUE IF NOT EXISTS '{reason}';")

    op.add_column(
        "fantasy_roster_slots",
        sa.Column("purchase_credits", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_fantasy_roster_slots_purchase_credits",
        "fantasy_roster_slots",
        "purchase_credits IS NULL OR purchase_credits >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_fantasy_roster_slots_purchase_credits",
        "fantasy_roster_slots",
        type_="check",
    )
    op.drop_column("fantasy_roster_slots", "purchase_credits")
