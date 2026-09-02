"""Sports poll run audit table for scheduler (EP04-06).

Revision ID: e2f8a1b0c016
Revises: d1e4f7a0b015
Create Date: 2026-08-05 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e2f8a1b0c016"
down_revision: str | Sequence[str] | None = "d1e4f7a0b015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sports_poll_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("window", sa.String(length=32), nullable=False),
        sa.Column("quota_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lock_token", sa.String(length=64), nullable=True),
        sa.Column("fixtures_considered", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("fixtures_polled", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("provider_requests", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sports_poll_runs")),
    )
    op.create_index(op.f("ix_sports_poll_runs_window"), "sports_poll_runs", ["window"], unique=False)
    op.create_index(op.f("ix_sports_poll_runs_status"), "sports_poll_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sports_poll_runs_status"), table_name="sports_poll_runs")
    op.drop_index(op.f("ix_sports_poll_runs_window"), table_name="sports_poll_runs")
    op.drop_table("sports_poll_runs")
