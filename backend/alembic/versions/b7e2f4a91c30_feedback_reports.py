"""Segnalazioni utente con allegati (feedback).

Revision ID: b7e2f4a91c30
Revises: 98ca03d4135d
Create Date: 2026-11-02 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2f4a91c30"
down_revision: str | Sequence[str] | None = "98ca03d4135d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "feedback_reports",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("page_context", sa.String(length=255), nullable=True),
        sa.Column("platform", sa.String(length=16), nullable=True),
        sa.Column("app_version", sa.String(length=32), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("operator_note", sa.Text(), nullable=True),
        sa.Column("handled_by_id", sa.UUID(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "category in ('bug','suggerimento','altro')",
            name=op.f("ck_feedback_reports_category"),
        ),
        sa.CheckConstraint(
            "status in ('new','in_review','resolved','dismissed')",
            name=op.f("ck_feedback_reports_status"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["handled_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_reports")),
    )
    op.create_index(
        "ix_feedback_reports_status_created_at",
        "feedback_reports",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_feedback_reports_user_id_created_at",
        "feedback_reports",
        ["user_id", "created_at"],
    )

    op.create_table(
        "feedback_attachments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("stored_name", sa.String(length=80), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("kind in ('image','video')", name=op.f("ck_feedback_attachments_kind")),
        sa.ForeignKeyConstraint(["report_id"], ["feedback_reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_attachments")),
    )
    op.create_index("ix_feedback_attachments_report_id", "feedback_attachments", ["report_id"])


def downgrade() -> None:
    op.drop_index("ix_feedback_attachments_report_id", table_name="feedback_attachments")
    op.drop_table("feedback_attachments")
    op.drop_index("ix_feedback_reports_user_id_created_at", table_name="feedback_reports")
    op.drop_index("ix_feedback_reports_status_created_at", table_name="feedback_reports")
    op.drop_table("feedback_reports")
