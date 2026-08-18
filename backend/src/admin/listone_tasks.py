"""Celery task for the platform-wide (admin panel) listone provider refresh (EP11-04b)."""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from admin.listone_service import PLATFORM_JOB_SCOPE, refresh_platform_listone
from app.worker import celery_app
from auth.exceptions import ValidationAuthError
from config.settings.loader import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from leagues.listone_refresh_progress import ListoneRefreshProgress, save_progress


@celery_app.task(name="admin.refresh_platform_listone_from_provider")
def refresh_platform_listone_task(*, job_id: str, season_year: int, actor_id: str) -> dict:
    """Run full catalog+roster+listone refresh for the platform and publish progress."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)

    def publish(percent: int, stage: str, message: str, *, status: str = "running") -> None:
        save_progress(
            ListoneRefreshProgress(
                job_id=job_id,
                league_id=PLATFORM_JOB_SCOPE,
                status=status,
                percent=percent,
                stage=stage,
                message=message,
            )
        )

    try:
        publish(1, "running", "Aggiornamento avviato…")
        with session_scope(factory) as session:
            result = refresh_platform_listone(
                session,
                season_year=season_year,
                on_progress=lambda percent, stage, message: publish(percent, stage, message),
            )
            save_progress(
                ListoneRefreshProgress(
                    job_id=job_id,
                    league_id=PLATFORM_JOB_SCOPE,
                    status="completed",
                    percent=100,
                    stage="completed",
                    message=result.message,
                    result=result.model_dump(by_alias=True, mode="json"),
                )
            )
            return {"status": "completed", "job_id": job_id, "actor_id": actor_id}
    except ValidationAuthError as exc:
        save_progress(
            ListoneRefreshProgress(
                job_id=job_id,
                league_id=PLATFORM_JOB_SCOPE,
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
                league_id=PLATFORM_JOB_SCOPE,
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
