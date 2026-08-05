"""Provider snapshots table for SPD adapter (EP04-01).

Revision ID: a1b2c3d4e567
Revises: e6f2a9b0c345
Create Date: 2026-08-04 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e567"
down_revision: str | Sequence[str] | None = "e6f2a9b0c345"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("endpoint", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('utc', now())"),
            nullable=False,
        ),
        sa.Column("page_current", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("page_total", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("results_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("rate_limit_remaining", sa.Integer(), nullable=True),
        sa.Column("rate_limit_limit", sa.Integer(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_snapshots")),
        sa.UniqueConstraint(
            "provider",
            "endpoint",
            "request_fingerprint",
            "payload_hash",
            name="uq_provider_snapshots_content",
        ),
    )
    op.create_index(
        "ix_provider_snapshots_fetched_at",
        "provider_snapshots",
        ["fetched_at"],
        unique=False,
    )
    op.create_index(
        "ix_provider_snapshots_endpoint",
        "provider_snapshots",
        ["provider", "endpoint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_provider_snapshots_endpoint", table_name="provider_snapshots")
    op.drop_index("ix_provider_snapshots_fetched_at", table_name="provider_snapshots")
    op.drop_table("provider_snapshots")
