"""Operator notification broadcasts (EP09-06).

Revision ID: d5a2b7c9e140
Revises: c4f1a9e2b836
Create Date: 2026-10-20 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d5a2b7c9e140"
down_revision: str | Sequence[str] | None = "c4f1a9e2b836"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_broadcasts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("deep_link", sa.String(length=200), nullable=True),
        sa.Column("channels", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audience", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audience_label", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recipient_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("push_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_notification_broadcasts_created_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_broadcasts")),
    )
    op.create_index(
        "ix_notification_broadcasts_status_scheduled_at",
        "notification_broadcasts",
        ["status", "scheduled_at"],
    )
    # Per contare consegnati/letti di un avviso: dedup_key LIKE 'broadcast:<id>:%'.
    op.create_index(
        "ix_notifications_dedup_key_prefix",
        "notifications",
        ["dedup_key"],
        postgresql_ops={"dedup_key": "text_pattern_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_dedup_key_prefix", table_name="notifications")
    op.drop_index(
        "ix_notification_broadcasts_status_scheduled_at", table_name="notification_broadcasts"
    )
    op.drop_table("notification_broadcasts")
