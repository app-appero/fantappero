"""Venue, arbitro, logo squadra e allenatore della formazione (EP13-P04 live fix).

Additiva e retrocompatibile: il provider espone già questi campi su
``/fixtures``, ``/teams`` e ``/fixtures/lineups``, ma non venivano
persistiti. Nessuna colonna esistente cambia semantica.

* ``fixtures.venue_name`` / ``venue_city`` / ``referee``
* ``clubs.logo_url``
* ``official_lineups.coach_name``

Revision ID: a1c4f6e9b382
Revises: d6f9a3b1c247
Create Date: 2026-08-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4f6e9b382"
down_revision: str | Sequence[str] | None = "d6f9a3b1c247"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FIXTURES = "fixtures"
_CLUBS = "clubs"
_LINEUPS = "official_lineups"


def upgrade() -> None:
    op.add_column(_FIXTURES, sa.Column("venue_name", sa.String(length=160), nullable=True))
    op.add_column(_FIXTURES, sa.Column("venue_city", sa.String(length=120), nullable=True))
    op.add_column(_FIXTURES, sa.Column("referee", sa.String(length=160), nullable=True))
    op.add_column(_CLUBS, sa.Column("logo_url", sa.String(length=320), nullable=True))
    op.add_column(_LINEUPS, sa.Column("coach_name", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column(_LINEUPS, "coach_name")
    op.drop_column(_CLUBS, "logo_url")
    op.drop_column(_FIXTURES, "referee")
    op.drop_column(_FIXTURES, "venue_city")
    op.drop_column(_FIXTURES, "venue_name")
