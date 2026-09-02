"""Quiet hours for external notification channels (EP09-05).

Revision ID: 1abdd05156d8
Revises: 80d763c9e61d
Create Date: 2026-08-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1abdd05156d8"
down_revision: str | Sequence[str] | None = "80d763c9e61d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("quiet_hours_start_hour", sa.Integer(), nullable=True),
    )
    op.add_column(
        "user_profiles",
        sa.Column("quiet_hours_end_hour", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_user_profiles_quiet_hours_start_hour"),
        "user_profiles",
        "quiet_hours_start_hour IS NULL OR quiet_hours_start_hour BETWEEN 0 AND 23",
    )
    op.create_check_constraint(
        op.f("ck_user_profiles_quiet_hours_end_hour"),
        "user_profiles",
        "quiet_hours_end_hour IS NULL OR quiet_hours_end_hour BETWEEN 0 AND 23",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_user_profiles_quiet_hours_end_hour"), "user_profiles", type_="check"
    )
    op.drop_constraint(
        op.f("ck_user_profiles_quiet_hours_start_hour"), "user_profiles", type_="check"
    )
    op.drop_column("user_profiles", "quiet_hours_end_hour")
    op.drop_column("user_profiles", "quiet_hours_start_hour")
