"""Telefono facoltativo nelle richieste di accesso dei non tester.

Revision ID: c6e8a0b2d347
Revises: b3d5f7a9c124
Create Date: 2026-11-17 19:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6e8a0b2d347"
down_revision: str | Sequence[str] | None = "b3d5f7a9c124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "tester_access_requests", "phone", existing_type=sa.String(length=30), nullable=True
    )


def downgrade() -> None:
    op.execute("UPDATE tester_access_requests SET phone = '' WHERE phone IS NULL")
    op.alter_column(
        "tester_access_requests", "phone", existing_type=sa.String(length=30), nullable=False
    )
