"""Asta a rilanci: log dei rilanci per lotto (EP08-09).

Append-only: ogni riga è un rilancio visibile a tutti i partecipanti nel
momento stesso in cui viene piazzato (a differenza delle buste chiuse, dove
gli importi restano nascosti fino alla risoluzione).

Revision ID: c3a4b5d6e7f8
Revises: c2a3b4d5e6f7
Create Date: 2026-09-03 00:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3a4b5d6e7f8"
down_revision: str | Sequence[str] | None = "c2a3b4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_live_raises",
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
        sa.Column("lot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fantasy_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_credits", sa.Integer(), nullable=False),
        sa.Column(
            "placed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_credits >= 1", name=op.f("ck_market_live_raises_amount")),
        sa.ForeignKeyConstraint(
            ["lot_id"],
            ["market_live_lots.id"],
            name=op.f("fk_market_live_raises_lot_id_market_live_lots"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fantasy_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_market_live_raises_fantasy_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_live_raises")),
    )
    op.create_index(
        "ix_market_live_raises_lot_id",
        "market_live_raises",
        ["lot_id", "placed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_market_live_raises_lot_id", table_name="market_live_raises")
    op.drop_table("market_live_raises")
