"""Round homologation status and correction audit actions (EP07-07).

Revision ID: f2b6d9c1a847
Revises: e1a4c7f930b5
Create Date: 2026-08-17 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2b6d9c1a847"
down_revision: str | Sequence[str] | None = "e1a4c7f930b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

fantasy_round_homologation_status = postgresql.ENUM(
    "provisional",
    "homologated",
    name="fantasy_round_homologation_status",
    create_type=False,
)


def upgrade() -> None:
    for action in ("fantasy_round_homologated", "fantasy_round_correction_applied"):
        op.execute(f"ALTER TYPE league_audit_action ADD VALUE IF NOT EXISTS '{action}';")

    fantasy_round_homologation_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "fantasy_rounds",
        sa.Column(
            "homologation_status",
            fantasy_round_homologation_status,
            server_default=sa.text("'provisional'"),
            nullable=False,
        ),
    )
    op.add_column(
        "fantasy_rounds",
        sa.Column("homologated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "fantasy_rounds",
        sa.Column("homologated_by_user_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "fantasy_rounds",
        sa.Column("homologation_formula_version", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_fantasy_rounds_homologated_by_user_id_users",
        "fantasy_rounds",
        "users",
        ["homologated_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Same convention as the other league_audit_action additions in this
    # project (e.g. d4e6f8a0b085): delete rows using the values this
    # migration added before any earlier migration's downgrade rebuilds the
    # enum type down to its own historical snapshot.
    op.execute(
        "DELETE FROM league_audit_events WHERE action::text IN "
        "('fantasy_round_homologated', 'fantasy_round_correction_applied')"
    )
    op.drop_constraint(
        "fk_fantasy_rounds_homologated_by_user_id_users",
        "fantasy_rounds",
        type_="foreignkey",
    )
    op.drop_column("fantasy_rounds", "homologation_formula_version")
    op.drop_column("fantasy_rounds", "homologated_by_user_id")
    op.drop_column("fantasy_rounds", "homologated_at")
    op.drop_column("fantasy_rounds", "homologation_status")
    fantasy_round_homologation_status.drop(op.get_bind(), checkfirst=True)
