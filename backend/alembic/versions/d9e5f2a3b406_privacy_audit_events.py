"""Privacy audit events and league membership history labels (EP02-04).

Revision ID: d9e5f2a3b406
Revises: c8d4e1f2a305
Create Date: 2026-07-29 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d9e5f2a3b406"
down_revision: str | Sequence[str] | None = "c8d4e1f2a305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

privacy_audit_action = postgresql.ENUM(
    "data_export",
    "account_delete",
    name="privacy_audit_action",
    create_type=False,
)


def upgrade() -> None:
    privacy_audit_action.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "league_memberships",
        sa.Column("historical_display_name", sa.String(length=80), nullable=True),
    )
    op.create_table(
        "privacy_audit_events",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
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
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("action", privacy_audit_action, nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_privacy_audit_events_actor_id"),
        "privacy_audit_events",
        ["actor_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_privacy_audit_events_user_id"),
        "privacy_audit_events",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_privacy_audit_events_user_id"), table_name="privacy_audit_events")
    op.drop_index(op.f("ix_privacy_audit_events_actor_id"), table_name="privacy_audit_events")
    op.drop_table("privacy_audit_events")
    op.drop_column("league_memberships", "historical_display_name")
    privacy_audit_action.drop(op.get_bind(), checkfirst=True)
