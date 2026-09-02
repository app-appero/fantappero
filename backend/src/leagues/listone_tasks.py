"""Celery task for async league listone provider refresh with progress."""

from __future__ import annotations

from uuid import UUID

import database.models  # noqa: F401 — register ORM mappers
from app.worker import celery_app
from auth.exceptions import ValidationAuthError
from auth.models.user import User
from authorization.context import LeagueAccess
from config.settings.loader import get_api_settings
from database.enums import LeagueMemberRole
from database.session import create_engine_from_url, create_session_factory, session_scope
from leagues.listone_refresh_progress import ListoneRefreshProgress, save_progress
from leagues.listone_service import LeagueListoneService
from leagues.models.league import League


@celery_app.task(name="leagues.refresh_listone_from_provider")
def refresh_league_listone_task(*, job_id: str, league_id: str, actor_id: str) -> dict:
    """Run full catalog+roster+listone refresh and publish percent progress."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)

    def publish(percent: int, stage: str, message: str, *, status: str = "running") -> None:
        save_progress(
            ListoneRefreshProgress(
                job_id=job_id,
                league_id=league_id,
                status=status,
                percent=percent,
                stage=stage,
                message=message,
            )
        )

    try:
        publish(1, "running", "Aggiornamento avviato…")
        with session_scope(factory) as session:
            league = session.get(League, UUID(league_id))
            user = session.get(User, UUID(actor_id))
            if league is None or user is None:
                save_progress(
                    ListoneRefreshProgress(
                        job_id=job_id,
                        league_id=league_id,
                        status="failed",
                        percent=0,
                        stage="failed",
                        message="Lega o utente non trovati.",
                        error_code="listone_refresh_job_not_found",
                    )
                )
                return {"status": "failed"}

            access = LeagueAccess(
                league=league,
                user=user,
                membership_role=LeagueMemberRole.OWNER,
            )
            service = LeagueListoneService(session)

            def on_progress(percent: int, stage: str, message: str) -> None:
                publish(percent, stage, message)

            result = service.refresh_from_provider(access, on_progress=on_progress)
            save_progress(
                ListoneRefreshProgress(
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
            ListoneRefreshProgress(
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
    except Exception:
        save_progress(
            ListoneRefreshProgress(
                job_id=job_id,
                league_id=league_id,
                status="failed",
                percent=0,
                stage="failed",
                message="Aggiornamento listone non riuscito.",
                error_code="listone_refresh_failed",
            )
        )
        raise
    finally:
        engine.dispose()
