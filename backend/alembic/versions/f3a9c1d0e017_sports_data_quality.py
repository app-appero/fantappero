"""Sports data quality issues and sync retry audit (EP04-07).

Revision ID: f3a9c1d0e017
Revises: e2f8a1b0c016
Create Date: 2026-08-05 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f3a9c1d0e017"
down_revision: str | Sequence[str] | None = "e2f8a1b0c016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sports_data_quality_issues",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(length=320), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'open'"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("fixture_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fixture_provider_id", sa.Integer(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
            name=op.f("fk_sports_data_quality_issues_fixture_id_fixtures"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sports_data_quality_issues")),
        sa.UniqueConstraint("fingerprint", name=op.f("uq_sports_data_quality_issues_fingerprint")),
    )
    op.create_index(
        op.f("ix_sports_data_quality_issues_kind"),
        "sports_data_quality_issues",
        ["kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_data_quality_issues_code"),
        "sports_data_quality_issues",
        ["code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_data_quality_issues_severity"),
        "sports_data_quality_issues",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_data_quality_issues_status"),
        "sports_data_quality_issues",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_data_quality_issues_fixture_id"),
        "sports_data_quality_issues",
        ["fixture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_data_quality_issues_fixture_provider_id"),
        "sports_data_quality_issues",
        ["fixture_provider_id"],
        unique=False,
    )

    op.create_table(
        "sports_data_sync_retries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fixture_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fixture_provider_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "trigger",
            sa.String(length=32),
            server_default=sa.text("'operator_retry'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column(
            "counters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["fixtures.id"],
            name=op.f("fk_sports_data_sync_retries_fixture_id_fixtures"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["issue_id"],
            ["sports_data_quality_issues.id"],
            name=op.f("fk_sports_data_sync_retries_issue_id_sports_data_quality_issues"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_sports_data_sync_retries_requested_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sports_data_sync_retries")),
    )
    op.create_index(
        op.f("ix_sports_data_sync_retries_issue_id"),
        "sports_data_sync_retries",
        ["issue_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_data_sync_retries_fixture_id"),
        "sports_data_sync_retries",
        ["fixture_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_data_sync_retries_fixture_provider_id"),
        "sports_data_sync_retries",
        ["fixture_provider_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_data_sync_retries_requested_by_user_id"),
        "sports_data_sync_retries",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sports_data_sync_retries_status"),
        "sports_data_sync_retries",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sports_data_sync_retries_status"),
        table_name="sports_data_sync_retries",
    )
    op.drop_index(
        op.f("ix_sports_data_sync_retries_requested_by_user_id"),
        table_name="sports_data_sync_retries",
    )
    op.drop_index(
        op.f("ix_sports_data_sync_retries_fixture_provider_id"),
        table_name="sports_data_sync_retries",
    )
    op.drop_index(
        op.f("ix_sports_data_sync_retries_fixture_id"),
        table_name="sports_data_sync_retries",
    )
    op.drop_index(
        op.f("ix_sports_data_sync_retries_issue_id"),
        table_name="sports_data_sync_retries",
    )
    op.drop_table("sports_data_sync_retries")

    op.drop_index(
        op.f("ix_sports_data_quality_issues_fixture_provider_id"),
        table_name="sports_data_quality_issues",
    )
    op.drop_index(
        op.f("ix_sports_data_quality_issues_fixture_id"),
        table_name="sports_data_quality_issues",
    )
    op.drop_index(
        op.f("ix_sports_data_quality_issues_status"),
        table_name="sports_data_quality_issues",
    )
    op.drop_index(
        op.f("ix_sports_data_quality_issues_severity"),
        table_name="sports_data_quality_issues",
    )
    op.drop_index(
        op.f("ix_sports_data_quality_issues_code"),
        table_name="sports_data_quality_issues",
    )
    op.drop_index(
        op.f("ix_sports_data_quality_issues_kind"),
        table_name="sports_data_quality_issues",
    )
    op.drop_table("sports_data_quality_issues")
