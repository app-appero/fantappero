"""Celery task for on-demand MVP fixture sync (EP04-05).

Automated pre/live/post polling is EP04-06 (`sports_data.scheduler`).
"""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.fixtures.sync import FixtureSyncResult, sync_mvp_fixtures_with_client
from sports_data.provider.client import build_client_from_settings


@celery_app.task(name="sports_data.sync_mvp_fixtures")
def sync_mvp_fixtures_task(
    include_details: bool = True,
    max_fixtures_per_league: int | None = None,
) -> dict[str, int]:
    """Sync calendar (+ optional events/lineups/stats) for MVP competitions."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with build_client_from_settings(settings) as client:
            with session_scope(factory) as session:
                result: FixtureSyncResult = sync_mvp_fixtures_with_client(
                    session,
                    client,
                    include_details=include_details,
                    max_fixtures_per_league=max_fixtures_per_league,
                )
    finally:
        engine.dispose()
    c = result.counters
    return {
        "fixtures_created": c.fixtures_created,
        "fixtures_updated": c.fixtures_updated,
        "events_created": c.events_created,
        "events_corrected": c.events_corrected,
        "events_retracted": c.events_retracted,
        "lineups_created": c.lineups_created,
        "stats_created": c.stats_created,
        "stats_corrected": c.stats_corrected,
    }
