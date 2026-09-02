"""Tactical moves for progressive lineup edits (EP06-05).

Revision ID: c3e5f7a9b074
Revises: b1c3d5e7f062
Create Date: 2026-08-14 12:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3e5f7a9b074"
down_revision: str | Sequence[str] | None = "b1c3d5e7f062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

tactical_move_status = postgresql.ENUM(
    "applied",
    name="tactical_move_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        "ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS 'fantasy_tactical_move_applied';"
    )

    tactical_move_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tactical_moves",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
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
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            tactical_move_status,
            server_default="applied",
            nullable=False,
        ),
        sa.Column(
            "from_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "to_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "sequence >= 1 AND sequence <= 3",
            name=op.f("ck_tactical_moves_sequence"),
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["lineup_submissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["used_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tactical_moves")),
        sa.UniqueConstraint(
            "submission_id",
            "sequence",
            name="uq_tactical_moves_submission_id_sequence",
        ),
    )
    op.create_index("ix_tactical_moves_submission_id", "tactical_moves", ["submission_id"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tactical_moves_submission_id")
    op.execute("DROP TABLE IF EXISTS tactical_moves")
    tactical_move_status.drop(op.get_bind(), checkfirst=True)
    op.execute(
        sa.text(
            "DELETE FROM league_audit_events WHERE action::text IN ('fantasy_tactical_move_applied')"
        )
    )
