"""Celery task for on-demand MVP sports catalog sync (EP04-02).

Scheduling/polling automation is EP04-06 — this task is invoked manually or by ops.
"""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.catalog.sync import CatalogSyncResult, sync_mvp_catalog_with_client
from sports_data.provider.client import build_client_from_settings


@celery_app.task(name="sports_data.sync_mvp_catalog")
def sync_mvp_catalog_task() -> dict[str, int]:
    """Sync five MVP competitions, current seasons and clubs from API-Football."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with build_client_from_settings(settings) as client:
            with session_scope(factory) as session:
                result: CatalogSyncResult = sync_mvp_catalog_with_client(session, client)
    finally:
        engine.dispose()
    c = result.counters
    return {
        "competitions_created": c.competitions_created,
        "competitions_updated": c.competitions_updated,
        "seasons_created": c.seasons_created,
        "seasons_updated": c.seasons_updated,
        "clubs_created": c.clubs_created,
        "clubs_updated": c.clubs_updated,
        "memberships_created": c.memberships_created,
    }
