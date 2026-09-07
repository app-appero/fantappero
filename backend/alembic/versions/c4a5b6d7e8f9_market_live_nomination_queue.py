"""Asta a rilanci: coda di chiamata prestabilita (EP08-09).

Popolata solo quando ``nomination_mode = SEQUENTIAL``: l'ordine fisso in cui
i calciatori vengono chiamati automaticamente. In modalità MANUAL resta
vuota — l'admin/delegato sceglie il prossimo calciatore ad ogni turno.

Revision ID: c4a5b6d7e8f9
Revises: c3a4b5d6e7f8
Create Date: 2026-09-03 00:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4a5b6d7e8f9"
down_revision: str | Sequence[str] | None = "c3a4b5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_live_nomination_queue",
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
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["market_sessions.id"],
            name=op.f("fk_market_live_nomination_queue_session_id_market_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_market_live_nomination_queue_athlete_id_athletes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_live_nomination_queue")),
        sa.UniqueConstraint(
            "session_id",
            "athlete_id",
            name=op.f("uq_market_live_nomination_queue_session_athlete"),
        ),
        sa.UniqueConstraint(
            "session_id",
            "position",
            name=op.f("uq_market_live_nomination_queue_session_position"),
        ),
    )
    op.create_index(
        "ix_market_live_nomination_queue_session_id",
        "market_live_nomination_queue",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_live_nomination_queue_session_id",
        table_name="market_live_nomination_queue",
    )
    op.drop_table("market_live_nomination_queue")
