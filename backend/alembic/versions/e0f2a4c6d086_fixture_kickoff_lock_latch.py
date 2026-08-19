"""Persist observed kickoff and lock latch for postponements (EP06-07).

Revision ID: e0f2a4c6d086
Revises: d4e6f8a0b085
Create Date: 2026-08-14 17:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e0f2a4c6d086"
down_revision: str | Sequence[str] | None = "d4e6f8a0b085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "fantasy_round_fixtures",
        sa.Column("observed_kickoff_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "fantasy_round_fixtures",
        sa.Column("lock_latched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE fantasy_round_fixtures AS link
        SET observed_kickoff_at = fixture.kickoff_at
        FROM fixtures AS fixture
        WHERE link.fixture_id = fixture.id
          AND link.observed_kickoff_at IS NULL
        """
    )
    op.execute(
        """
        UPDATE fantasy_round_fixtures AS link
        SET lock_latched_at = fixture.kickoff_at
        FROM fixtures AS fixture
        WHERE link.fixture_id = fixture.id
          AND link.lock_latched_at IS NULL
          AND link.excluded_at IS NULL
          AND fixture.kickoff_at IS NOT NULL
          AND fixture.kickoff_at <= timezone('utc', now())
          AND upper(fixture.status_short) NOT IN ('PST', 'CANC', 'ABD', 'AWD', 'WO')
        """
    )
    op.create_index(
        op.f("ix_roster_import_sessions_actor_id"),
        "roster_import_sessions",
        ["actor_id"],
    )
    op.create_index(
        op.f("ix_roster_turn_snapshots_actor_id"),
        "roster_turn_snapshots",
        ["actor_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_roster_turn_snapshots_actor_id"),
        table_name="roster_turn_snapshots",
    )
    op.drop_index(
        op.f("ix_roster_import_sessions_actor_id"),
        table_name="roster_import_sessions",
    )
    op.drop_column("fantasy_round_fixtures", "lock_latched_at")
    op.drop_column("fantasy_round_fixtures", "observed_kickoff_at")
