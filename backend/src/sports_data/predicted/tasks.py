"""Job giornaliero delle formazioni probabili."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from observability.logging import get_logger
from sports_data.predicted.client import FotmobClient
from sports_data.predicted.sync import PredictedSyncSummary, sync_predicted_lineups

logger = get_logger(__name__)


def _summary_payload(summary: PredictedSyncSummary) -> dict[str, object]:
    return {
        "fixtures_considered": summary.fixtures_considered,
        "matches_linked": summary.matches_linked,
        "snapshots_saved": summary.snapshots_saved,
        "skipped_recent": summary.skipped_recent,
        "skipped_unmatched": summary.skipped_unmatched,
        "rejected": summary.rejected,
        "warnings": summary.warnings,
        "requests_made": summary.requests_made,
        "message": summary.message,
    }


def run_predicted_lineup_sync(
    *,
    force: bool = False,
    league_id: str | None = None,
    manual: bool = False,
) -> dict[str, object]:
    from system_jobs.service import allow_periodic

    settings = get_api_settings()
    # Il cron rispetta l'interruttore del pannello. Il pulsante operatore
    # (`manual`) e il giro di una singola lega partono comunque.
    if not manual and league_id is None and not allow_periodic(
        "sports-predicted-lineups",
        settings.predicted_lineups_enabled,
    ):
        return {}
    key = settings.resolved_rapidapi_key()
    client = (
        None
        if key is None
        else FotmobClient(
            key,
            base_url=settings.fotmob_base_url,
            timeout_seconds=settings.fotmob_timeout_seconds,
            max_retries=settings.fotmob_max_retries,
        )
    )
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            summary = sync_predicted_lineups(
                session,
                client,
                horizon=timedelta(days=4),
                max_lineup_calls=settings.fotmob_max_lineup_calls,
                force=force,
                league_id=None if league_id is None else UUID(league_id),
                min_age=timedelta(hours=settings.predicted_lineups_min_age_hours),
            )
    finally:
        if client is not None:
            client.close()
        engine.dispose()
    return _summary_payload(summary)


@celery_app.task(name="sports_data.sync_predicted_lineups")
def sync_predicted_lineups_task() -> dict[str, object]:
    return run_predicted_lineup_sync()
