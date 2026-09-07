"""Trade proposal: optional expiry (EP08-05 / FR-MKT-03).

A proposal with no expiry never expires on its own — it stays "proposed"
until someone acts on it (accept/reject/counter) or the proposer cancels it.

Revision ID: 193ad998313a
Revises: d6e7f8a9b0c1
Create Date: 2026-09-07 13:31:49.031902
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "193ad998313a"
down_revision: str | Sequence[str] | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("trade_proposals", "expires_at", nullable=True)


def downgrade() -> None:
    # A proposal saved without an expiry while this revision was applied has no
    # real deadline to restore. Same convention as other irreversible-narrowing
    # downgrades in this codebase (e.g. the enum-value migrations, which delete
    # the rows that used the new value): resolve it explicitly here rather than
    # let the NOT NULL backfill fail outright — 30 days from creation is an
    # arbitrary but harmless placeholder, never read as a real deadline again
    # once forward-migrated.
    op.execute(
        "UPDATE trade_proposals SET expires_at = created_at + INTERVAL '30 days' "
        "WHERE expires_at IS NULL"
    )
    op.alter_column("trade_proposals", "expires_at", nullable=False)
