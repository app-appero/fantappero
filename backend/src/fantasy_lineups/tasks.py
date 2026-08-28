"""Celery task per la formazione automatica dei fantallenatori IA (EP13-P05).

Idempotente per costruzione: la formula è deterministica e il servizio non
tocca né le squadre umane né le formazioni già schierate a mano. Rieseguire il
task sullo stesso turno non produce effetti diversi.
"""

from __future__ import annotations

from sqlalchemy import select

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings.loader import get_api_settings
from database.enums import FantasyTurnStatus, LeagueState
from database.session import create_engine_from_url, create_session_factory, session_scope
from fantasy_lineups.ai_service import run_ai_lineups_for_round
from fantasy_turns.models import FantasyRound
from leagues.models.league import League
from observability.logging import get_logger

logger = get_logger(__name__)

#: Stati turno per cui ha senso schierare: prima del lock definitivo.
_OPEN_STATUSES = (FantasyTurnStatus.SCHEDULED, FantasyTurnStatus.OPEN)


@celery_app.task(name="fantasy_lineups.generate_ai")
def generate_ai_lineups_task() -> dict[str, int]:
    """Schiera le squadre IA dei turni aperti di tutte le leghe attive."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)

    rounds_processed = 0
    teams_updated = 0
    teams_skipped = 0

    try:
        with session_scope(factory) as session:
            rows = session.execute(
                select(FantasyRound.id, FantasyRound.league_id)
                .join(League, League.id == FantasyRound.league_id)
                .where(
                    League.state == LeagueState.ACTIVE,
                    FantasyRound.status.in_(_OPEN_STATUSES),
                )
                .order_by(FantasyRound.league_id.asc(), FantasyRound.number.asc())
            ).all()

            for round_id, league_id in rows:
                results = run_ai_lineups_for_round(
                    session,
                    league_id=league_id,
                    round_id=round_id,
                )
                rounds_processed += 1
                for item in results:
                    if item.outcome in {"created", "updated"}:
                        teams_updated += 1
                    else:
                        teams_skipped += 1
    finally:
        engine.dispose()

    logger.info(
        "ai_lineups_task_completed",
        extra={
            "rounds": rounds_processed,
            "teams_updated": teams_updated,
            "teams_skipped": teams_skipped,
        },
    )
    return {
        "rounds": rounds_processed,
        "teamsUpdated": teams_updated,
        "teamsSkipped": teams_skipped,
    }
