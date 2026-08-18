"""Sealed-bid market session and bids for the initial auction (EP08-01).

Revision ID: a1c3e5f7b902
Revises: f2b6d9c1a847
Create Date: 2026-08-18 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c3e5f7b902"
down_revision: str | Sequence[str] | None = "f2b6d9c1a847"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "market_session_created",
    "market_session_closed",
    "market_bid_submitted",
    "market_bid_withdrawn",
)

market_session_kind = postgresql.ENUM(
    "initial_auction",
    name="market_session_kind",
    create_type=False,
)
market_session_status = postgresql.ENUM(
    "scheduled",
    "open",
    "closed",
    "resolved",
    name="market_session_status",
    create_type=False,
)
market_bid_status = postgresql.ENUM(
    "submitted",
    "expired",
    "won",
    "lost",
    "cancelled",
    name="market_bid_status",
    create_type=False,
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    market_session_kind.create(op.get_bind(), checkfirst=True)
    market_session_status.create(op.get_bind(), checkfirst=True)
    market_bid_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "market_sessions",
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
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", market_session_kind, nullable=False),
        sa.Column("status", market_session_status, server_default="scheduled", nullable=False),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "closes_at > opens_at", name=op.f("ck_market_sessions_window_order")
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_market_sessions_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_market_sessions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_sessions")),
    )
    op.create_index(
        "ix_market_sessions_league_id", "market_sessions", ["league_id"], unique=False
    )
    op.create_index("ix_market_sessions_status", "market_sessions", ["status"], unique=False)

    op.create_table(
        "market_bids",
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
        sa.Column("fantasy_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_credits", sa.Integer(), nullable=False),
        sa.Column("status", market_bid_status, server_default="submitted", nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount_credits >= 1", name=op.f("ck_market_bids_amount_credits")
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["market_sessions.id"],
            name=op.f("fk_market_bids_session_id_market_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fantasy_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_market_bids_fantasy_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_market_bids_athlete_id_athletes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_bids")),
        sa.UniqueConstraint(
            "session_id",
            "fantasy_team_id",
            "athlete_id",
            name=op.f("uq_market_bids_session_team_athlete"),
        ),
    )
    op.create_index("ix_market_bids_session_id", "market_bids", ["session_id"], unique=False)
    op.create_index("ix_market_bids_athlete_id", "market_bids", ["athlete_id"], unique=False)
    op.create_index(
        "ix_market_bids_fantasy_team_id", "market_bids", ["fantasy_team_id"], unique=False
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM league_audit_events
        WHERE action::text IN (
            'market_session_created',
            'market_session_closed',
            'market_bid_submitted',
            'market_bid_withdrawn'
        );
        """
    )
    op.drop_index("ix_market_bids_fantasy_team_id", table_name="market_bids")
    op.drop_index("ix_market_bids_athlete_id", table_name="market_bids")
    op.drop_index("ix_market_bids_session_id", table_name="market_bids")
    op.drop_table("market_bids")
    op.drop_index("ix_market_sessions_status", table_name="market_sessions")
    op.drop_index("ix_market_sessions_league_id", table_name="market_sessions")
    op.drop_table("market_sessions")
    op.execute("DROP TYPE IF EXISTS market_bid_status;")
    op.execute("DROP TYPE IF EXISTS market_session_status;")
    op.execute("DROP TYPE IF EXISTS market_session_kind;")
