"""User entitlements and subscription payments (EP11-01/02).

Revision ID: 3eae5a327551
Revises: 94321d5a16fa
Create Date: 2026-08-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3eae5a327551"
down_revision: str | Sequence[str] | None = "94321d5a16fa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUBSCRIPTION_PLAN = postgresql.ENUM(
    "free", "pro", name="subscription_plan", create_type=False
)
_SUBSCRIPTION_PAYMENT_STATUS = postgresql.ENUM(
    "completed", name="subscription_payment_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    _SUBSCRIPTION_PLAN.create(bind, checkfirst=True)
    _SUBSCRIPTION_PAYMENT_STATUS.create(bind, checkfirst=True)

    op.create_table(
        "user_entitlements",
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan", _SUBSCRIPTION_PLAN, server_default=sa.text("'free'"), nullable=False),
        sa.Column("active_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_entitlements_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_entitlements")),
    )

    op.create_table(
        "subscription_payments",
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
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_code", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("external_event_id", sa.Text(), nullable=False),
        sa.Column(
            "status",
            _SUBSCRIPTION_PAYMENT_STATUS,
            server_default=sa.text("'completed'"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_subscription_payments_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_payments")),
        sa.UniqueConstraint(
            "external_event_id", name="uq_subscription_payments_external_event_id"
        ),
    )
    op.create_index(
        "ix_subscription_payments_user_id", "subscription_payments", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_payments_user_id", table_name="subscription_payments")
    op.drop_table("subscription_payments")
    op.drop_table("user_entitlements")
    bind = op.get_bind()
    _SUBSCRIPTION_PAYMENT_STATUS.drop(bind, checkfirst=True)
    _SUBSCRIPTION_PLAN.drop(bind, checkfirst=True)
