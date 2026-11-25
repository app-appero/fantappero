"""Sostituto dopo uno scambio sbilanciato: registro ``trade_replacements`` (1.5, 25/11).

Uno scambio eseguito che lascia una squadra sotto la misura della rosa (es. 2 per 1, 34/35) le
dà il diritto di comprare un calciatore libero del ruolo che manca, al suo Valore, anche a
mercato chiuso. Una riga per ogni posto da riempire: lega, squadra, scambio, ruolo, stato (da
scegliere / scelto / annullato), calciatore preso, prezzo e date. Nuova azione di audit
``market_trade_replacement_purchased`` per lo storico del mercato.

Il downgrade toglie la tabella, il tipo dello stato e gli eventi di audit dell'acquisto (il
valore dell'enum di audit resta, come nelle altre migrazioni: Postgres non toglie un valore).

Revision ID: c3e8a5f17b24
Revises: bed6529e6ba1
Create Date: 2026-11-25 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3e8a5f17b24"
down_revision: str | Sequence[str] | None = "bed6529e6ba1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_VALUES = ("pending", "chosen", "cancelled")
_AUDIT_ACTION = "market_trade_replacement_purchased"


def upgrade() -> None:
    op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{_AUDIT_ACTION}';")
    status_enum = postgresql.ENUM(*_STATUS_VALUES, name="trade_replacement_status")
    status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "trade_replacements",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("league_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fantasy_team_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trade_proposal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("P", "D", "C", "A", name="fantasy_role", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*_STATUS_VALUES, name="trade_replacement_status", create_type=False),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("athlete_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("price_credits", sa.Integer(), nullable=True),
        sa.Column("chosen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "price_credits IS NULL OR price_credits >= 0",
            name=op.f("ck_trade_replacements_price_credits"),
        ),
        sa.ForeignKeyConstraint(
            ["athlete_id"],
            ["athletes.id"],
            name=op.f("fk_trade_replacements_athlete_id_athletes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["fantasy_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_trade_replacements_fantasy_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["league_id"],
            ["leagues.id"],
            name=op.f("fk_trade_replacements_league_id_leagues"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trade_proposal_id"],
            ["trade_proposals.id"],
            name=op.f("fk_trade_replacements_trade_proposal_id_trade_proposals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trade_replacements")),
    )
    op.create_index("ix_trade_replacements_league_id", "trade_replacements", ["league_id"])
    op.create_index(
        "ix_trade_replacements_team_status",
        "trade_replacements",
        ["fantasy_team_id", "status"],
    )
    op.create_index(
        "ix_trade_replacements_trade_proposal_id", "trade_replacements", ["trade_proposal_id"]
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM league_audit_events WHERE action::text = '{_AUDIT_ACTION}';")
    op.drop_index("ix_trade_replacements_trade_proposal_id", table_name="trade_replacements")
    op.drop_index("ix_trade_replacements_team_status", table_name="trade_replacements")
    op.drop_index("ix_trade_replacements_league_id", table_name="trade_replacements")
    op.drop_table("trade_replacements")
    postgresql.ENUM(name="trade_replacement_status").drop(op.get_bind(), checkfirst=True)
