"""User profiles and preferences (EP02-02).

Revision ID: b7c3d9e2f104
Revises: a4b2c8d1e903
Create Date: 2026-07-29 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7c3d9e2f104"
down_revision: str | Sequence[str] | None = "a4b2c8d1e903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=80), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=16), server_default="it", nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="Europe/Rome",
            nullable=False,
        ),
        sa.Column(
            "notifications_email",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "notifications_push",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("policy_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(length=32), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_profiles")
