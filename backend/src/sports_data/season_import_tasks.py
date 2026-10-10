"""Celery task: on-demand full season import (catalog + fixtures) for MVP competitions.

Independent of any league — meant to run at season kickoff (or on-demand to
unblock a league created before the periodic sync caught up), so league
creation and "Genera calendario" always find data already in the DB instead
of calling the provider inline.
"""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from config.settings.loader import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from fantasy_turns.calendar_refresh_progress import CalendarRefreshProgress, save_progress
from observability.logging import get_logger
from sports_data.catalog.sync import sync_mvp_catalog_with_client
from sports_data.fixtures.sync import sync_mvp_fixtures_with_client
from sports_data.provider.client import build_client_from_settings
from sports_data.provider.errors import (
    PROVIDER_RATE_LIMITED_USER_MESSAGE,
    PROVIDER_UNAVAILABLE_USER_MESSAGE,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
)

logger = get_logger(__name__)

PLATFORM_SCOPE = "platform"


@celery_app.task(name="sports_data.import_season")
def import_season_task(*, job_id: str, actor_id: str | None) -> dict:
    """Sincronizza catalogo + calendario fixture per tutte le competizioni MVP.

    Comando admin "Importa calendario stagione": stessa coppia di sync del
    giro automatico periodico, qui come override manuale puntuale (es. a
    inizio stagione, prima ancora che esista una lega).
    """
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)

    def publish(percent: int, stage: str, message: str, *, status: str = "running") -> None:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=PLATFORM_SCOPE,
                status=status,
                percent=percent,
                stage=stage,
                message=message,
            )
        )

    try:
        publish(1, "catalog", "Sincronizzazione catalogo competizioni…")
        with build_client_from_settings(settings) as client:
            with session_scope(factory) as session:
                catalog_result = sync_mvp_catalog_with_client(session, client)

            publish(50, "fixtures", "Sincronizzazione calendario fixture…")
            with session_scope(factory) as session:
                fixtures_result = sync_mvp_fixtures_with_client(
                    session,
                    client,
                    include_details=False,
                )

        totals = {
            "seasonsCreated": catalog_result.counters.seasons_created,
            "seasonsUpdated": catalog_result.counters.seasons_updated,
            "competitionsUpdated": catalog_result.counters.competitions_updated,
            "fixturesCreated": fixtures_result.counters.fixtures_created,
            "fixturesUpdated": fixtures_result.counters.fixtures_updated,
        }
        message = (
            f"Stagioni create: {totals['seasonsCreated']}, aggiornate: {totals['seasonsUpdated']}. "
            f"Fixture nuove: {totals['fixturesCreated']}, aggiornate: {totals['fixturesUpdated']}."
        )
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=PLATFORM_SCOPE,
                status="completed",
                percent=100,
                stage="completed",
                message=message,
                result=totals,
            )
        )

        if fixtures_result.counters.fixtures_created > 0 or fixtures_result.counters.fixtures_updated > 0:
            try:
                from fantasy_turns.tasks import ensure_upcoming_fantasy_turns_task

                ensure_upcoming_fantasy_turns_task.delay()
            except Exception:
                logger.exception("fantasy_turns_ensure_enqueue_failed")

        return {"status": "completed", "job_id": job_id, "actor_id": actor_id}
    except ProviderRateLimitError:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=PLATFORM_SCOPE,
                status="failed",
                percent=0,
                stage="failed",
                message=PROVIDER_RATE_LIMITED_USER_MESSAGE,
                error_code="provider_rate_limited",
            )
        )
        return {"status": "failed", "code": "provider_rate_limited"}
    except ProviderAuthError:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=PLATFORM_SCOPE,
                status="failed",
                percent=0,
                stage="failed",
                message=PROVIDER_UNAVAILABLE_USER_MESSAGE,
                error_code="provider_auth_failed",
            )
        )
        return {"status": "failed", "code": "provider_auth_failed"}
    except ProviderError:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=PLATFORM_SCOPE,
                status="failed",
                percent=0,
                stage="failed",
                message="Importazione calendario stagione non riuscita dal provider sportivo.",
                error_code="provider_sync_failed",
            )
        )
        return {"status": "failed", "code": "provider_sync_failed"}
    except Exception:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=PLATFORM_SCOPE,
                status="failed",
                percent=0,
                stage="failed",
                message="Importazione calendario stagione non riuscita.",
                error_code="season_import_failed",
            )
        )
        raise
    finally:
        engine.dispose()
