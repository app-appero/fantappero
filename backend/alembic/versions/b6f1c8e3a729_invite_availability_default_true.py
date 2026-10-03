"""Default coaches to available for named invites.

Pilot feedback: none of the first recruited testers showed up in the
directory because the column defaulted to ``false`` and nobody had a reason
to discover the toggle before being invited. Flip the default to ``true``
and backfill existing profiles that never opted out explicitly.

Revision ID: b6f1c8e3a729
Revises: a1c4e8f2b6d3
Create Date: 2026-10-03 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6f1c8e3a729"
down_revision: str | Sequence[str] | None = "a1c4e8f2b6d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "user_profiles",
        "available_for_invites",
        server_default=sa.text("true"),
    )
    op.execute(
        "UPDATE user_profiles SET available_for_invites = TRUE "
        "WHERE available_for_invites = FALSE;"
    )


def downgrade() -> None:
    op.alter_column(
        "user_profiles",
        "available_for_invites",
        server_default=sa.text("false"),
    )
