"""Mappatura esplicita giornata H2H → finestra europea (EP13-P03).

Additiva e retrocompatibile:

* tre colonne nullable su ``league_calendars`` (cicli e impronta finestre);
* nuova tabella ``league_calendar_round_windows``.

Nessun dato viene cancellato o riscritto. I calendari già generati restano
validi con i campi a ``NULL`` e continuano a essere letti con la vecchia
corrispondenza per numero progressivo finché non vengono rigenerati.

Revision ID: c5e8a1f3d229
Revises: b4d7e2f9c118
Create Date: 2026-08-23 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e8a1f3d229"
down_revision: str | Sequence[str] | None = "b4d7e2f9c118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CALENDARS = "league_calendars"
_ROUND_WINDOWS = "league_calendar_round_windows"


def upgrade() -> None:
    op.add_column(_CALENDARS, sa.Column("cycle_length", sa.Integer(), nullable=True))
    op.add_column(_CALENDARS, sa.Column("cycle_count", sa.Integer(), nullable=True))
    op.add_column(
        _CALENDARS,
        sa.Column("windows_fingerprint", sa.String(length=64), nullable=True),
    )

    op.create_table(
        _ROUND_WINDOWS,
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('utc', now())"),
        ),
        sa.Column("calendar_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("cycle_round_number", sa.Integer(), nullable=False),
        sa.Column("window_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_kind", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["calendar_id"],
            [f"{_CALENDARS}.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "calendar_id",
            "round_number",
            name="uq_league_calendar_round_windows_round",
        ),
        sa.UniqueConstraint(
            "calendar_id",
            "window_start_at",
            name="uq_league_calendar_round_windows_window",
        ),
        sa.CheckConstraint(
            "round_number > 0",
            name="ck_league_calendar_round_windows_round",
        ),
        sa.CheckConstraint(
            "window_end_at > window_start_at",
            name="ck_league_calendar_round_windows_order",
        ),
    )
    op.create_index(
        "ix_league_calendar_round_windows_calendar_id",
        _ROUND_WINDOWS,
        ["calendar_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_league_calendar_round_windows_calendar_id", table_name=_ROUND_WINDOWS)
    op.drop_table(_ROUND_WINDOWS)
    op.drop_column(_CALENDARS, "windows_fingerprint")
    op.drop_column(_CALENDARS, "cycle_count")
    op.drop_column(_CALENDARS, "cycle_length")
