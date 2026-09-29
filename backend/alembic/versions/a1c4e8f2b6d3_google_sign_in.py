"""Google Sign-In identity on users (EP02-01 extension).

Revision ID: a1c4e8f2b6d3
Revises: 37c365bf2399
Create Date: 2026-09-29 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4e8f2b6d3"
down_revision: str | Sequence[str] | None = "37c365bf2399"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    op.create_check_constraint(
        "ck_users_has_credential",
        "users",
        "password_hash IS NOT NULL OR google_sub IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_has_credential", "users", type_="check")
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    # Google-only accounts have no password_hash; downgrading drops the
    # feature, so give them an unusable placeholder instead of failing.
    op.execute(
        "UPDATE users SET password_hash = 'google-only-account-migrated-back' "
        "WHERE password_hash IS NULL"
    )
    op.drop_column("users", "google_sub")
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
