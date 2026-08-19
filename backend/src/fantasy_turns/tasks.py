"""Celery tasks for automatic european turn generation."""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings.loader import get_api_settings, validate_worker_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from fantasy_turns.service import FantasyTurnService
from observability.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(name="fantasy_turns.ensure_upcoming")
def ensure_upcoming_fantasy_turns_task() -> dict[str, int]:
    """Materialize upcoming weekend/midweek turns for all ACTIVE leagues."""
    try:
        worker = validate_worker_settings()
        horizon = worker.fantasy_turns_horizon_days
        enabled = worker.fantasy_turns_auto_generate_enabled
    except Exception:
        api = get_api_settings()
        horizon = api.fantasy_turns_horizon_days
        enabled = api.fantasy_turns_auto_generate_enabled

    if not enabled:
        logger.info("fantasy_turns_ensure_skipped_disabled")
        return {
            "leagues": 0,
            "created": 0,
            "opened": 0,
            "upgraded": 0,
            "duplicates": 0,
            "waiting": 0,
        }

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            totals = FantasyTurnService(session).ensure_upcoming_for_active_leagues(
                horizon_days=horizon,
                auto_open=True,
            )
    finally:
        engine.dispose()
    logger.info("fantasy_turns_ensure_task_done", extra=totals)
    return totals
