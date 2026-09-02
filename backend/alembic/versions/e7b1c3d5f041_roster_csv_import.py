"""CSV roster import sessions and audit action (EP05-04).

Revision ID: e7b1c3d5f041
Revises: d6a9c2e4f032
Create Date: 2026-08-11 15:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7b1c3d5f041"
down_revision: str | Sequence[str] | None = "d6a9c2e4f032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = ("fantasy_roster_csv_imported",)

roster_import_status = postgresql.ENUM(
    "draft",
    "confirmed",
    name="roster_import_status",
    create_type=False,
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    roster_import_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "roster_import_sessions",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("league_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            roster_import_status,
            nullable=False,
            server_default="draft",
        ),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("preview_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["league_id"], ["leagues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("row_count >= 0", name="ck_roster_import_sessions_row_count"),
        sa.CheckConstraint("error_count >= 0", name="ck_roster_import_sessions_error_count"),
        sa.CheckConstraint("warning_count >= 0", name="ck_roster_import_sessions_warning_count"),
    )
    op.create_index(
        "ix_roster_import_sessions_league_id",
        "roster_import_sessions",
        ["league_id"],
    )
    op.create_index(
        "ix_roster_import_sessions_status",
        "roster_import_sessions",
        ["status"],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM league_audit_events WHERE action::text = 'fantasy_roster_csv_imported'"
        )
    )
    op.drop_index("ix_roster_import_sessions_status", table_name="roster_import_sessions")
    op.drop_index("ix_roster_import_sessions_league_id", table_name="roster_import_sessions")
    op.drop_table("roster_import_sessions")
    roster_import_status.drop(op.get_bind(), checkfirst=True)
