"""Job asincrono per il voto statistico (EP07-01)."""

from __future__ import annotations

from uuid import UUID

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings.loader import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from fantasy_ratings.service import compute_fixture_ratings
from observability.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="fantasy_ratings.compute_fixture")
def compute_fixture_ratings_task(
    fixture_id: str | None = None,
    fixture_provider_id: int | None = None,
    league_id: str | None = None,
    minutes_threshold: int | None = None,
) -> dict[str, int | str]:
    """Calcola e persiste i voti statistici di una fixture (idempotente)."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            result = compute_fixture_ratings(
                session,
                fixture_id=UUID(fixture_id) if fixture_id else None,
                fixture_provider_id=fixture_provider_id,
                league_id=UUID(league_id) if league_id else None,
                minutes_threshold=minutes_threshold,
            )
    finally:
        engine.dispose()
    payload = {
        "fixture_id": str(result.fixture_id),
        "fixture_provider_id": result.fixture_provider_id,
        "formula_version": result.formula_version,
        "created": result.counters.created,
        "updated": result.counters.updated,
        "unchanged": result.counters.unchanged,
        "removed": result.counters.removed,
    }
    logger.info("fantasy_ratings_compute_task_done", extra=payload)
    return payload
