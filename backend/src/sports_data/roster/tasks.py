"""Celery task for on-demand MVP roster sync (EP04-03).

Scheduling/polling automation is EP04-06 — this task is invoked manually or by ops.
"""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from sports_data.provider.client import build_client_from_settings
from sports_data.roster.sync import RosterSyncResult, sync_mvp_roster_with_client


@celery_app.task(name="sports_data.sync_mvp_roster")
def sync_mvp_roster_task() -> dict[str, int]:
    """Sync athletes, squads and transfers for MVP clubs from API-Football."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with build_client_from_settings(settings) as client:
            with session_scope(factory) as session:
                result: RosterSyncResult = sync_mvp_roster_with_client(session, client)
    finally:
        engine.dispose()
    c = result.counters
    return {
        "athletes_created": c.athletes_created,
        "athletes_updated": c.athletes_updated,
        "memberships_created": c.memberships_created,
        "memberships_updated": c.memberships_updated,
        "transfers_created": c.transfers_created,
    }
