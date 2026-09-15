"""Read the operational market-open flag without requiring the migration.

``leagues.market_open`` is mapped as a deferred column so ordinary League loads
keep working on an unmigrated database. Callers that need the flag use these
helpers, which treat a missing column as open (the product default).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Boolean, bindparam, select, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from leagues.models.league import League

MARKET_GATE_UNAVAILABLE_CODE = "market_gate_unavailable"
MARKET_GATE_UNAVAILABLE_MESSAGE = (
    "Impossibile aggiornare lo stato del mercato. "
    "Esegui la migrazione del database (alembic upgrade head)."
)


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


def write_market_open(session: Session, league_id: UUID, open_flag: bool) -> None:
    """Persist the flag with raw SQL so a deferred ORM load is not required.

    A missing column must become a clear 400, not an unhandled 500 that the
    browser reports as a failed connection.
    """
    stmt = text("UPDATE leagues SET market_open = :open WHERE id = :id").bindparams(
        bindparam("open", type_=Boolean()),
        bindparam("id", type_=PGUUID(as_uuid=True)),
    )
    try:
        result = session.execute(stmt, {"open": open_flag, "id": league_id})
    except DBAPIError as exc:
        session.rollback()
        raise ValidationAuthError(
            MARKET_GATE_UNAVAILABLE_MESSAGE,
            code=MARKET_GATE_UNAVAILABLE_CODE,
        ) from exc
    if result.rowcount == 0:
        raise ValidationAuthError("Lega non trovata.", code="league_not_found")
