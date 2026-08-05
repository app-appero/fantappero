"""Celery task for on-demand official listone generation (EP04-04)."""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.listone.generate import ListoneGenerateResult, generate_official_listone


@celery_app.task(name="sports_data.generate_official_listone")
def generate_official_listone_task(season_year: int) -> dict[str, int | str]:
    """Generate/refresh official listone role assignments for a season year."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            result: ListoneGenerateResult = generate_official_listone(
                session,
                season_year=season_year,
            )
    finally:
        engine.dispose()
    c = result.counters
    return {
        "season_year": result.season_year,
        "mapping_version": result.mapping_version,
        "created": c.created,
        "updated": c.updated,
        "unchanged": c.unchanged,
        "skipped_unmapped": c.skipped_unmapped,
        "deactivated": c.deactivated,
    }
