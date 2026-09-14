"""Asta a rilanci: modalità "a turno", alfabetico per ruolo, casuale (EP08-09).

Aggiunge tre nuovi valori a ``market_live_nomination_mode``:

- ``turn_based``: a ogni chiamata tocca a un fantasy team diverso, secondo una
  rotazione fissa estratta a sorte alla creazione della sessione e conservata
  nella nuova tabella ``market_live_turn_order`` (un ruolo simmetrico a
  ``market_live_nomination_queue``, ma di squadre anziché di calciatori).
- ``alphabetical_by_role`` / ``random``: riusano la coda già esistente
  (``market_live_nomination_queue``), generata automaticamente lato server
  invece che caricata dall'admin — nessuna nuova tabella richiesta per queste
  due.

Revision ID: d0a2c4e6f813
Revises: 193ad998313a
Create Date: 2026-09-08 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0a2c4e6f813"
down_revision: str | Sequence[str] | None = "193ad998313a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_NOMINATION_MODES = ("turn_based", "alphabetical_by_role", "random")


def upgrade() -> None:
    for value in _NEW_NOMINATION_MODES:
        op.execute(f"ALTER TYPE market_live_nomination_mode ADD VALUE IF NOT EXISTS '{value}';")

    op.create_table(
        "market_live_turn_order",
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
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["market_sessions.id"],
            name=op.f("fk_market_live_turn_order_session_id_market_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fantasy_team_id"],
            ["fantasy_teams.id"],
            name=op.f("fk_market_live_turn_order_fantasy_team_id_fantasy_teams"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_live_turn_order")),
        sa.UniqueConstraint(
            "session_id",
            "fantasy_team_id",
            name=op.f("uq_market_live_turn_order_session_team"),
        ),
        sa.UniqueConstraint(
            "session_id",
            "position",
            name=op.f("uq_market_live_turn_order_session_position"),
        ),
    )
    op.create_index(
        "ix_market_live_turn_order_session_id",
        "market_live_turn_order",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_market_live_turn_order_session_id",
        table_name="market_live_turn_order",
    )
    op.drop_table("market_live_turn_order")
    # Postgres enum values cannot be dropped individually; left in place on
    # downgrade (same convention already used by other migrations in this
    # codebase, e.g. c5b6c7d8e9fa_market_live_swap.py).

