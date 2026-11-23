"""Tipi delle competizioni del fornitore: campionato o coppa (release 1.3).

- ``provider_competition_types``: una riga per competizione del fornitore (``/leagues``) con il
  tipo ``league`` o ``cup``. La media stagionale e il Valore di mercato contano solo le righe
  di campionato dello storico (decisione di Rosario, 22/11); le coppe restano nella carriera.

Solo una tabella nuova: il downgrade la toglie senza toccare il resto. La tabella nasce vuota:
si riempie col primo passo dell'import dello storico (una chiamata).

Revision ID: 70b4367fdb66
Revises: f3a5c7e9b1d4
Create Date: 2026-11-22 23:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "70b4367fdb66"
down_revision: str | Sequence[str] | None = "f3a5c7e9b1d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_competition_types",
        sa.Column("provider_id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
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
            "type IN ('league', 'cup')",
            name=op.f("ck_provider_competition_types_type"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["provider_snapshots.id"],
            name=op.f("fk_provider_competition_types_snapshot_id_provider_snapshots"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("provider_id", name=op.f("pk_provider_competition_types")),
    )


def downgrade() -> None:
    op.drop_table("provider_competition_types")
