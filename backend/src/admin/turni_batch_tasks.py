"""Task Celery di «Esegui tutti» nel pannello operatore › Turni (release 1.5)."""

from __future__ import annotations

import database.models  # noqa: F401 — register ORM mappers
from admin.turni_batch import RUN_BATCH_TASK, run_batch
from app.worker import celery_app


@celery_app.task(name=RUN_BATCH_TASK)
def run_turni_batch_task(*, batch_id: str, actor_id: str) -> dict[str, object]:
    """Esegue le operazioni dei turni una dopo l'altra e pubblica l'avanzamento (Redis)."""
    progress = run_batch(batch_id, actor_id)
    return {
        "batch_id": batch_id,
        "status": progress.status,
        "ok": progress.count("ok"),
        "failed": progress.count("failed"),
        "skipped": progress.count("skipped"),
    }
