"""Platform roles for authorization (EP02-03).

Revision ID: c8d4e1f2a305
Revises: b7c3d9e2f104
Create Date: 2026-07-29 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c8d4e1f2a305"
down_revision: str | Sequence[str] | None = "b7c3d9e2f104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

platform_role = postgresql.ENUM(
    "user",
    "operator",
    name="platform_role",
    create_type=False,
)


def upgrade() -> None:
    platform_role.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "platform_role",
            platform_role,
            nullable=False,
            server_default="user",
        ),
    )
    op.alter_column("users", "platform_role", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "platform_role")
    platform_role.drop(op.get_bind(), checkfirst=True)
