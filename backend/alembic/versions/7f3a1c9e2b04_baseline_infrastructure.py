"""Baseline infrastructure schema (EP01-06).

Revision ID: 7f3a1c9e2b04
Revises:
Create Date: 2026-07-28 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "7f3a1c9e2b04"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

flag_scope = postgresql.ENUM("system", "tenant", name="flag_scope", create_type=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    flag_scope.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "system_flags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "scope",
            flag_scope,
            server_default=sa.text("'system'"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_flags")),
        sa.UniqueConstraint("key", name=op.f("uq_system_flags_key")),
    )
    op.create_index(op.f("ix_system_flags_scope"), "system_flags", ["scope"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_system_flags_scope"), table_name="system_flags")
    op.drop_table("system_flags")
    flag_scope.drop(op.get_bind(), checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
