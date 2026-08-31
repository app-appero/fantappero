"""Celery tasks for automatic european turn generation."""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from auth.exceptions import ValidationAuthError
from config.settings.loader import get_api_settings, validate_worker_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from fantasy_turns.calendar_refresh_progress import CalendarRefreshProgress, save_progress
from fantasy_turns.service import FantasyTurnService
from leagues.models.league import League
from observability.logging import get_logger
from sports_data.provider.errors import ProviderAuthError, ProviderError, ProviderRateLimitError

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


@celery_app.task(name="fantasy_turns.refresh_full_calendar_active_leagues")
def refresh_full_calendar_active_leagues_task() -> dict[str, int]:
    """Giro periodico automatico di "Aggiorna calendario" per tutte le leghe attive.

    Copre l'intera stagione (non solo l'orizzonte di `ensure_upcoming`), così
    una fixture "da aggiornare" che riceve una data lontana nel tempo entra
    comunque in un turno senza che l'admin debba premere il pulsante. Il
    pulsante resta disponibile per un aggiornamento immediato su richiesta.
    """
    try:
        worker = validate_worker_settings()
        enabled = worker.fantasy_turns_full_refresh_enabled
    except Exception:
        api = get_api_settings()
        enabled = api.fantasy_turns_full_refresh_enabled

    if not enabled:
        logger.info("fantasy_calendar_refresh_periodic_skipped_disabled")
        return {"leagues": 0, "refreshed": 0, "failed": 0}

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            totals = FantasyTurnService(session).refresh_full_calendar_for_active_leagues()
    finally:
        engine.dispose()
    return totals


@celery_app.task(name="fantasy_turns.refresh_full_calendar_from_provider")
def refresh_full_calendar_task(*, job_id: str, league_id: str, actor_id: str | None) -> dict:
    """Comando admin "Aggiorna calendario": sync provider + backfill stagionale."""
    from uuid import UUID

    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)

    def publish(percent: int, stage: str, message: str, *, status: str = "running") -> None:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=league_id,
                status=status,
                percent=percent,
                stage=stage,
                message=message,
            )
        )

    try:
        publish(1, "running", "Aggiornamento calendario avviato…")
        with session_scope(factory) as session:
            league = session.get(League, UUID(league_id))
            if league is None:
                save_progress(
                    CalendarRefreshProgress(
                        job_id=job_id,
                        league_id=league_id,
                        status="failed",
                        percent=0,
                        stage="failed",
                        message="Lega non trovata.",
                        error_code="league_not_found",
                    )
                )
                return {"status": "failed", "code": "league_not_found"}
            result = FantasyTurnService(session).refresh_full_calendar(
                league,
                actor_id=UUID(actor_id) if actor_id else None,
                on_progress=lambda percent, stage, message: publish(percent, stage, message),
            )
            save_progress(
                CalendarRefreshProgress(
                    job_id=job_id,
                    league_id=league_id,
                    status="completed",
                    percent=100,
                    stage="completed",
                    message=result.message,
                    result=result.model_dump(by_alias=True, mode="json"),
                )
            )
            return {"status": "completed", "job_id": job_id}
    except ValidationAuthError as exc:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=league_id,
                status="failed",
                percent=0,
                stage="failed",
                message=exc.message,
                error_code=exc.code,
            )
        )
        return {"status": "failed", "code": exc.code}
    except ProviderRateLimitError:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=league_id,
                status="failed",
                percent=0,
                stage="failed",
                message="Quota API-Football esaurita o rate limit attivo. Riprova tra poco.",
                error_code="provider_rate_limited",
            )
        )
        return {"status": "failed", "code": "provider_rate_limited"}
    except ProviderAuthError:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=league_id,
                status="failed",
                percent=0,
                stage="failed",
                message="Autenticazione provider rifiutata. Verifica API_FOOTBALL_KEY.",
                error_code="provider_auth_failed",
            )
        )
        return {"status": "failed", "code": "provider_auth_failed"}
    except ProviderError:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=league_id,
                status="failed",
                percent=0,
                stage="failed",
                message="Aggiornamento calendario non riuscito dal provider sportivo.",
                error_code="provider_sync_failed",
            )
        )
        return {"status": "failed", "code": "provider_sync_failed"}
    except Exception:
        save_progress(
            CalendarRefreshProgress(
                job_id=job_id,
                league_id=league_id,
                status="failed",
                percent=0,
                stage="failed",
                message="Aggiornamento calendario non riuscito.",
                error_code="calendar_refresh_failed",
            )
        )
        raise
    finally:
        engine.dispose()
