"""Famiglia dei rinnovi di sessione (revoca a catena sul riuso).

Revision ID: d7f9b1c3e458
Revises: c6e8a0b2d347
Create Date: 2026-11-18 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7f9b1c3e458"
down_revision: str | Sequence[str] | None = "c6e8a0b2d347"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auth_sessions", sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_index("ix_auth_sessions_family_id", "auth_sessions", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_family_id", table_name="auth_sessions")
    op.drop_column("auth_sessions", "family_id")
