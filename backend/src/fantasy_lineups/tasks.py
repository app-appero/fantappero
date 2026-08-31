"""Celery task per la formazione automatica dei fantallenatori IA (EP13-P05).

Idempotente per costruzione: la formula è deterministica e il servizio non
tocca né le squadre umane né le formazioni già schierate a mano. Rieseguire il
task sullo stesso turno non produce effetti diversi.
"""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings.loader import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from fantasy_lineups.ai_service import generate_ai_lineups_for_active_leagues
from observability.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="fantasy_lineups.generate_ai")
def generate_ai_lineups_task() -> dict[str, int]:
    """Schiera le squadre IA dei turni aperti di tutte le leghe attive."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)

    try:
        with session_scope(factory) as session:
            result = generate_ai_lineups_for_active_leagues(session)
    finally:
        engine.dispose()

    logger.info(
        "ai_lineups_task_completed",
        extra={
            "rounds": result["rounds"],
            "teams_updated": result["teamsUpdated"],
            "teams_skipped": result["teamsSkipped"],
        },
    )
    return result
