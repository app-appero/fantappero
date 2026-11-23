"""Job periodico «Medie e Valore di mercato» (release 1.3).

Ricalcola, per ogni stagione con leghe in corso, lo storico FantApperò della stagione, la media
stagionale e il Valore di tutto il listone. Gira spesso (default ogni ora) ma lavora solo quando
voti, statistiche, storico o listone sono cambiati (impronta): dopo ogni giornata il Valore
segue i voti nuovi.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings.loader import get_api_settings
from database.enums import LeagueState
from database.session import create_engine_from_url, create_session_factory, session_scope
from leagues.models.league import League
from market.valuation_service import refresh_market_values
from observability.logging import get_logger
from sports_data.listone.models import RoleAssignment

logger = get_logger(__name__)

REFRESH_MARKET_VALUES_TASK = "market.refresh_market_values"
_LIVE_LEAGUE_STATES = (
    LeagueState.DRAFT,
    LeagueState.CONFIGURING,
    LeagueState.AUCTION,
    LeagueState.ACTIVE,
)


def seasons_to_refresh(session: Session) -> list[int]:
    """Stagioni delle leghe non concluse, più l'ultima del listone (anche senza leghe)."""
    years = {
        int(year)
        for year in session.scalars(
            select(League.season_year).where(League.state.in_(_LIVE_LEAGUE_STATES)).distinct()
        ).all()
    }
    latest = session.scalar(select(func.max(RoleAssignment.season_year)))
    if latest is not None:
        years.add(int(latest))
    return sorted(years)


@celery_app.task(name=REFRESH_MARKET_VALUES_TASK)
def refresh_market_values_task(
    season_year: int | None = None,
    force: bool = False,
) -> dict[str, object]:
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    results: list[dict[str, object]] = []
    try:
        with session_scope(factory) as session:
            years = [season_year] if season_year is not None else seasons_to_refresh(session)
            for year in years:
                results.append(
                    refresh_market_values(session, season_year=year, force=force).as_dict()
                )
    finally:
        engine.dispose()
    logger.info("market_values_task_done", extra={"seasons": [r["seasonYear"] for r in results]})
    return {"status": "completed", "results": results}
