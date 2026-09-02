"""Roster composition status columns (EP05-05).

Revision ID: f8c2d4e6a052
Revises: e7b1c3d5f041
Create Date: 2026-08-11 18:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8c2d4e6a052"
down_revision: str | Sequence[str] | None = "e7b1c3d5f041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_AUDIT_ACTIONS = ("fantasy_roster_composition_validated",)

roster_composition_status = postgresql.ENUM(
    "incomplete",
    "invalid",
    "validated",
    name="roster_composition_status",
    create_type=False,
)


def upgrade() -> None:
    for action in _NEW_AUDIT_ACTIONS:
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    roster_composition_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "fantasy_teams",
        sa.Column(
            "composition_status",
            roster_composition_status,
            nullable=False,
            server_default="incomplete",
        ),
    )
    op.add_column(
        "fantasy_teams",
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_fantasy_teams_composition_status",
        "fantasy_teams",
        ["composition_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_fantasy_teams_composition_status", table_name="fantasy_teams")
    op.drop_column("fantasy_teams", "validated_at")
    op.drop_column("fantasy_teams", "composition_status")
    roster_composition_status.drop(op.get_bind(), checkfirst=True)
    op.execute(
        sa.text(
            "DELETE FROM league_audit_events "
            "WHERE action::text = 'fantasy_roster_composition_validated'"
        )
    )
