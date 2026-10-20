"""Expo push device tokens (EP09-05).

Revision ID: c4f1a9e2b836
Revises: b3d6f8a1c925
Create Date: 2026-10-19 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4f1a9e2b836"
down_revision: str | Sequence[str] | None = "b3d6f8a1c925"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_devices",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_push_devices_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_push_devices")),
        sa.UniqueConstraint("token", name="uq_push_devices_token"),
    )
    op.create_index(
        op.f("ix_push_devices_user_id"),
        "push_devices",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_push_devices_user_id"), table_name="push_devices")
    op.drop_table("push_devices")
