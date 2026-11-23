"""Job Celery dell'import dello storico stagioni dal fornitore (pannello operatore, 1.3)."""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from admin.season_history_service import SEASON_HISTORY_JOB_SCOPE, import_season_history
from app.worker import celery_app
from auth.exceptions import ValidationAuthError
from config.settings.loader import get_api_settings
from database.session import create_engine_from_url, create_session_factory, session_scope
from leagues.listone_refresh_progress import ListoneRefreshProgress, save_progress

IMPORT_SEASON_HISTORY_TASK = "admin.import_season_history_from_provider"


@celery_app.task(name=IMPORT_SEASON_HISTORY_TASK)
def import_season_history_task(
    *,
    job_id: str,
    season_year: int,
    max_calls: int,
    actor_id: str,
) -> dict:
    """Esegue l'import e pubblica l'avanzamento. Salva dopo ogni chiamata (riprendibile)."""
    settings = get_api_settings()
    engine = create_engine_from_url(settings.database_url)
    factory = create_session_factory(engine)

    def publish(
        percent: int,
        stage: str,
        message: str,
        *,
        status: str = "running",
        result: dict | None = None,
        error_code: str | None = None,
    ) -> None:
        save_progress(
            ListoneRefreshProgress(
                job_id=job_id,
                league_id=SEASON_HISTORY_JOB_SCOPE,
                status=status,
                percent=percent,
                stage=stage,
                message=message,
                result=result,
                error_code=error_code,
            )
        )

    try:
        publish(1, "running", "Import dello storico avviato…")
        with session_scope(factory) as session:
            result = import_season_history(
                session,
                season_year=season_year,
                max_calls=max_calls,
                on_progress=lambda percent, stage, message: publish(percent, stage, message),
                checkpoint=session.commit,
            )
            publish(
                100,
                "completed",
                result.message,
                status="completed",
                result=result.model_dump(by_alias=True, mode="json"),
            )
            return {"status": "completed", "job_id": job_id, "actor_id": actor_id}
    except ValidationAuthError as exc:
        publish(0, "failed", exc.message, status="failed", error_code=exc.code)
        return {"status": "failed", "code": exc.code}
    except Exception:
        publish(
            0,
            "failed",
            "Import dello storico non riuscito.",
            status="failed",
            error_code="season_history_import_failed",
        )
        raise
    finally:
        engine.dispose()
