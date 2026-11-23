"""Uso dell'app per utente: piattaforma, versione, prima e ultima volta (release 1.4).

- ``user_app_usage``: una riga per (utente, piattaforma) con la versione dell'app (nome e
  versionCode) e da dove si sa (intestazioni dell'app 1.4, ``GET /app/version`` delle app 1.2 e
  1.3, User-Agent ``okhttp/`` delle app più vecchie), prima e ultima volta visto nell'app.

Decisione di Rosario del 23/11 (elenco «chi ha quale versione» del pannello operatore e
notifica della nuova versione solo a chi non ce l'ha già). Una sola tabella nuova, vuota: si
riempie con l'uso dell'app dopo il rilascio. Il downgrade la toglie senza toccare il resto.

Revision ID: b7c4e2a91d35
Revises: 3f0f09518f28
Create Date: 2026-11-23 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7c4e2a91d35"
down_revision: str | Sequence[str] | None = "3f0f09518f28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_app_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("version_name", sa.String(length=32), nullable=True),
        sa.Column("version_code", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
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
            "source IN ('header', 'version_check', 'user_agent')",
            name=op.f("ck_user_app_usage_source"),
        ),
        sa.CheckConstraint(
            "platform IN ('android', 'ios')", name=op.f("ck_user_app_usage_platform")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_app_usage_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_app_usage")),
        sa.UniqueConstraint("user_id", "platform", name="uq_user_app_usage_user_platform"),
    )


def downgrade() -> None:
    op.drop_table("user_app_usage")
