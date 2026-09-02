"""Trade proposals between fantasy teams (EP08-05 / FR-MKT-03).

Revision ID: e5a8c0d2f346
Revises: d4f7b9c1e235
Create Date: 2026-08-18 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e5a8c0d2f346"
down_revision: str | Sequence[str] | None = "d4f7b9c1e235"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "market_trade_proposed",
    "market_trade_cancelled",
)

trade_status = postgresql.ENUM(
    "proposed",
    "cancelled",
    "expired",
    name="trade_status",
    create_type=False,
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    trade_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "trade_proposals",
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
        sa.Column("proposer_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offered_athlete_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "requested_athlete_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "offered_credits", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "requested_credits", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("status", trade_status, server_default="proposed", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "offered_credits >= 0", name=op.f("ck_trade_proposals_offered_credits")
        ),
        sa.CheckConstraint(
            "requested_credits >= 0", name=op.f("ck_trade_proposals_requested_credits")
        ),
        sa.CheckConstraint(
            "proposer_team_id != recipient_team_id",
            name=op.f("ck_trade_proposals_distinct_teams"),
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_trade_proposals_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["proposer_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_trade_proposals_proposer_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_trade_proposals_recipient_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_trade_proposals_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trade_proposals")),
    )
    op.create_index(
        "ix_trade_proposals_league_id", "trade_proposals", ["league_id"], unique=False
    )
    op.create_index(
        "ix_trade_proposals_proposer_team_id",
        "trade_proposals",
        ["proposer_team_id"],
        unique=False,
    )
    op.create_index(
        "ix_trade_proposals_recipient_team_id",
        "trade_proposals",
        ["recipient_team_id"],
        unique=False,
    )
    op.create_index("ix_trade_proposals_status", "trade_proposals", ["status"], unique=False)


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM league_audit_events
        WHERE action::text IN ('market_trade_proposed', 'market_trade_cancelled');
        """
    )
    op.drop_index("ix_trade_proposals_status", table_name="trade_proposals")
    op.drop_index("ix_trade_proposals_recipient_team_id", table_name="trade_proposals")
    op.drop_index("ix_trade_proposals_proposer_team_id", table_name="trade_proposals")
    op.drop_index("ix_trade_proposals_league_id", table_name="trade_proposals")
    op.drop_table("trade_proposals")
    op.execute("DROP TYPE IF EXISTS trade_status;")
