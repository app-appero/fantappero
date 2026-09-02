"""Foto giocatore dal provider (EP13-P04-quinquies).

Additiva e retrocompatibile: API-Football espone già `player.photo` su
`/players/squads` e `/players`, ma non veniva persistito.

Revision ID: c7f2a4d6e831
Revises: b5e8c2d4f019
Create Date: 2026-08-29 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7f2a4d6e831"
down_revision: str | Sequence[str] | None = "b5e8c2d4f019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ATHLETES = "athletes"


def upgrade() -> None:
    op.add_column(_ATHLETES, sa.Column("photo_url", sa.String(length=320), nullable=True))


def downgrade() -> None:
    op.drop_column(_ATHLETES, "photo_url")
