"""Asta a rilanci: lotti (un calciatore alla volta) (EP08-09).

Revision ID: c2a3b4d5e6f7
Revises: c1a2b3d4e5f6
Create Date: 2026-09-03 00:05:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2a3b4d5e6f7"
down_revision: str | Sequence[str] | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

market_live_lot_status = postgresql.ENUM(
    "open",
    "sold",
    "passed",
    "cancelled",
    name="market_live_lot_status",
    create_type=False,
)


def upgrade() -> None:
    market_live_lot_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "market_live_lots",
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
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("status", market_live_lot_status, server_default="open", nullable=False),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("min_increment_credits", sa.Integer(), nullable=False),
        sa.Column("current_leader_team_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "current_amount_credits", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "current_amount_credits >= 0", name=op.f("ck_market_live_lots_amount")
        ),
        sa.CheckConstraint(
            "min_increment_credits >= 1", name=op.f("ck_market_live_lots_min_increment")
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["market_sessions.id"],
            name=op.f("fk_market_live_lots_session_id_market_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_market_live_lots_athlete_id_athletes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["current_leader_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_market_live_lots_current_leader_team_id_fantasy_teams"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_live_lots")),
        sa.UniqueConstraint(
            "session_id",
            "sequence_number",
            name=op.f("uq_market_live_lots_session_sequence"),
        ),
    )
    op.create_index(
        "ix_market_live_lots_session_id", "market_live_lots", ["session_id"], unique=False
    )
    op.create_index(
        "ix_market_live_lots_status",
        "market_live_lots",
        ["session_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_market_live_lots_session_athlete_active",
        "market_live_lots",
        ["session_id", "athlete_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('open', 'sold')"),
    )


def downgrade() -> None:
    op.drop_index("uq_market_live_lots_session_athlete_active", table_name="market_live_lots")
    op.drop_index("ix_market_live_lots_status", table_name="market_live_lots")
    op.drop_index("ix_market_live_lots_session_id", table_name="market_live_lots")
    op.drop_table("market_live_lots")
    op.execute("DROP TYPE IF EXISTS market_live_lot_status;")
