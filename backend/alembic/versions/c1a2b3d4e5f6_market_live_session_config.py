"""Asta a rilanci: configurazione sulla sessione di mercato (EP08-09).

Aggiunge il valore 'live_auction' a MarketSessionKind e le colonne di
configurazione (tutte nullable) usate solo da quelle sessioni: modalità di
chiamata, incremento minimo, finestra di soft-close/durata lotto, delegato.
Additiva: le sessioni sealed esistenti non sono toccate.

Revision ID: c1a2b3d4e5f6
Revises: b4d8e19a5f36
Create Date: 2026-09-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c1a2b3d4e5f6"
down_revision: str | Sequence[str] | None = "b4d8e19a5f36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = (
    "market_live_session_created",
    "market_live_session_started",
    "market_live_lot_nominated",
    "market_live_raise_placed",
    "market_live_lot_sold",
    "market_live_lot_passed",
    "market_live_lot_cancelled",
    "market_live_session_ended",
)

market_live_nomination_mode = postgresql.ENUM(
    "manual",
    "sequential",
    name="market_live_nomination_mode",
    create_type=False,
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")
    op.execute("ALTER TYPE market_session_kind ADD VALUE IF NOT EXISTS 'live_auction';")

    market_live_nomination_mode.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "market_sessions",
        sa.Column("nomination_mode", market_live_nomination_mode, nullable=True),
    )
    op.add_column(
        "market_sessions",
        sa.Column("min_increment_credits", sa.Integer(), nullable=True),
    )
    op.add_column(
        "market_sessions",
        sa.Column("soft_close_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "market_sessions",
        sa.Column("lot_duration_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "market_sessions",
        sa.Column("operator_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_market_sessions_operator_user_id_users"),
        "market_sessions",
        "users",
        ["operator_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # kind::text avoids Postgres's "unsafe use of new enum value before commit":
    # 'live_auction' was just added to market_session_kind in this same transaction.
    op.create_check_constraint(
        "ck_market_sessions_live_fields",
        "market_sessions",
        "kind::text <> 'live_auction' OR ("
        "nomination_mode IS NOT NULL AND min_increment_credits IS NOT NULL "
        "AND soft_close_seconds IS NOT NULL AND lot_duration_seconds IS NOT NULL"
        ")",
    )
    op.create_check_constraint(
        "ck_market_sessions_min_increment_credits",
        "market_sessions",
        "min_increment_credits IS NULL OR min_increment_credits >= 1",
    )
    op.create_check_constraint(
        "ck_market_sessions_soft_close_seconds",
        "market_sessions",
        "soft_close_seconds IS NULL OR soft_close_seconds BETWEEN 5 AND 120",
    )
    op.create_check_constraint(
        "ck_market_sessions_lot_duration_seconds",
        "market_sessions",
        "lot_duration_seconds IS NULL OR lot_duration_seconds BETWEEN 10 AND 300",
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM league_audit_events
        WHERE action::text IN ('{"', '".join(_NEW_AUDIT_ACTIONS)}');
        """
    )
    op.drop_constraint(
        "ck_market_sessions_lot_duration_seconds", "market_sessions", type_="check"
    )
    op.drop_constraint("ck_market_sessions_soft_close_seconds", "market_sessions", type_="check")
    op.drop_constraint(
        "ck_market_sessions_min_increment_credits", "market_sessions", type_="check"
    )
    op.drop_constraint("ck_market_sessions_live_fields", "market_sessions", type_="check")
    op.drop_constraint(
        op.f("fk_market_sessions_operator_user_id_users"),
        "market_sessions",
        type_="foreignkey",
    )
    op.drop_column("market_sessions", "operator_user_id")
    op.drop_column("market_sessions", "lot_duration_seconds")
    op.drop_column("market_sessions", "soft_close_seconds")
    op.drop_column("market_sessions", "min_increment_credits")
    op.drop_column("market_sessions", "nomination_mode")
    op.execute("DROP TYPE IF EXISTS market_live_nomination_mode;")
    # Postgres enum values (market_session_kind='live_auction', the new audit
    # actions) cannot be dropped individually; left in place on downgrade, same
    # convention already used by other migrations in this codebase.
