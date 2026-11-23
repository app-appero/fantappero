"""Uso del sito da Android in ``user_app_usage`` (release 1.4, Rosario 23/11).

La notifica «È disponibile la versione X dell'app» va a chi usa l'app Android e a chi visita il
sito da un telefono Android (non dal computer o da iPhone). Le visite del sito da Android si
scrivono nella stessa tabella, con la piattaforma ``web-android`` e la fonte ``browser``: qui si
allargano solo i due vincoli CHECK. Nessun dato cambia; il downgrade toglie le righe del sito
da Android e rimette i vincoli di prima.

Revision ID: bed6529e6ba1
Revises: b7c4e2a91d35
Create Date: 2026-11-23 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "bed6529e6ba1"
down_revision: str | Sequence[str] | None = "b7c4e2a91d35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "user_app_usage"
_SOURCE = "ck_user_app_usage_source"
_PLATFORM = "ck_user_app_usage_platform"


def _replace_checks(*, sources: str, platforms: str) -> None:
    op.drop_constraint(op.f(_SOURCE), _TABLE, type_="check")
    op.drop_constraint(op.f(_PLATFORM), _TABLE, type_="check")
    op.create_check_constraint(op.f(_SOURCE), _TABLE, f"source IN ({sources})")
    op.create_check_constraint(op.f(_PLATFORM), _TABLE, f"platform IN ({platforms})")


def upgrade() -> None:
    _replace_checks(
        sources="'header', 'version_check', 'user_agent', 'browser'",
        platforms="'android', 'ios', 'web-android'",
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM {_TABLE} WHERE platform = 'web-android' OR source = 'browser'")
    _replace_checks(
        sources="'header', 'version_check', 'user_agent'",
        platforms="'android', 'ios'",
    )
