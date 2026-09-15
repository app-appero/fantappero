"""Read the operational market-open flag without requiring the migration.

``leagues.market_open`` is mapped as a deferred column so ordinary League loads
keep working on an unmigrated database. Callers that need the flag use these
helpers, which treat a missing column as open (the product default).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from leagues.models.league import League


def read_market_open(session: Session, league_id: UUID, *, default: bool = True) -> bool:
    flags = read_market_open_map(session, [league_id], default=default)
    return flags.get(league_id, default)


def read_market_open_map(
    session: Session,
    league_ids: Sequence[UUID],
    *,
    default: bool = True,
) -> dict[UUID, bool]:
    if not league_ids:
        return {}
    try:
        rows = session.execute(
            select(League.id, League.market_open).where(League.id.in_(league_ids))
        ).all()
    except ProgrammingError:
        session.rollback()
        return {}
    return {row.id: bool(row.market_open) if row.market_open is not None else default for row in rows}
