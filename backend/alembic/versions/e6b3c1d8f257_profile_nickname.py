"""Nickname pubblico dell'utente (univoco senza maiuscole).

Revision ID: e6b3c1d8f257
Revises: d5a2b7c9e140
Create Date: 2026-10-21 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6b3c1d8f257"
down_revision: str | Sequence[str] | None = "d5a2b7c9e140"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("nickname", sa.String(length=30), nullable=True))
    op.create_index(
        "uq_user_profiles_nickname_lower",
        "user_profiles",
        [sa.text("lower(nickname)")],
        unique=True,
        postgresql_where=sa.text("nickname IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_profiles_nickname_lower", table_name="user_profiles")
    op.drop_column("user_profiles", "nickname")
