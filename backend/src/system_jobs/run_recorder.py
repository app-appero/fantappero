"""Scrive l'esito di ogni giro dei job periodici (release 1.4, «Da guardare»).

Agganciato ai segnali di Celery (``task_prerun`` / ``task_failure`` / ``task_postrun``): i task
dei job non cambiano. Vale solo per i task del catalogo ``system_jobs.catalog``; un giro che
``allow_periodic`` salta perché il job è spento non si scrive (lo segna
``mark_current_run_skipped``).

La scrittura usa una connessione sua, dopo la fine del task: un errore qui finisce nel log e
non tocca mai il job né il suo risultato.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from celery.signals import task_failure, task_postrun, task_prerun

from observability.logging import get_logger
from system_jobs.running import current_task_id, mark_started_by_worker, release
from system_jobs.runs import (
    OUTCOME_FAILED,
    RunOutcome,
    job_key_for_task,
    outcome_from_result,
    reason_from_exception,
    record_run,
)

logger = get_logger(__name__)

_MAX_TRACKED = 1000

#: task_id → (chiave del job, inizio, perf_counter all'inizio)
_running: dict[str, tuple[str, datetime, float]] = {}
_skipped: set[str] = set()
_failures: dict[str, BaseException | None] = {}


def _task_name(task: Any, sender: Any = None) -> str | None:
    for candidate in (task, sender):
        name = getattr(candidate, "name", None)
        if name:
            return str(name)
    return None


def mark_current_run_skipped() -> None:
    """Il giro in corso non conta: il job è spento (chiamato da ``allow_periodic``)."""
    task_id = current_task_id()
    if task_id is not None and task_id in _running:
        _skipped.add(task_id)


@task_prerun.connect
def _on_task_prerun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    **_extra: Any,
) -> None:
    job_key = job_key_for_task(_task_name(task, sender))
    if job_key is None or not task_id:
        return
    if len(_running) >= _MAX_TRACKED:
        # Task mai finiti (worker interrotto a metà): si dimenticano i più vecchi.
        for stale in list(_running)[: _MAX_TRACKED // 2]:
            _running.pop(stale, None)
            _skipped.discard(stale)
            _failures.pop(stale, None)
    _running[task_id] = (job_key, datetime.now(UTC), time.perf_counter())
    # Redis dice al pannello (e al lancio a mano) che il job sta girando.
    mark_started_by_worker(job_key, task_id)


@task_failure.connect
def _on_task_failure(
    sender: Any = None,
    task_id: str | None = None,
    exception: BaseException | None = None,
    **_extra: Any,
) -> None:
    if task_id and task_id in _running:
        _failures[task_id] = exception


@task_postrun.connect
def _on_task_postrun(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    retval: Any = None,
    state: str | None = None,
    **_extra: Any,
) -> None:
    if not task_id:
        return
    try:
        _record_finished_run(task_id, retval, state)
    finally:
        # Il segno «in esecuzione» si toglie dopo aver scritto l'esito: quando il pannello vede il
        # job fermo, l'ultimo esito è già quello nuovo. Vale anche per un giro saltato (job
        # spento) o non finito.
        job_key = job_key_for_task(_task_name(task, sender))
        if job_key is not None:
            release(job_key, task_id)


def _record_finished_run(task_id: str, retval: Any, state: str | None) -> None:
    started = _running.pop(task_id, None)
    skipped = task_id in _skipped
    _skipped.discard(task_id)
    failed = task_id in _failures
    exception = _failures.pop(task_id, None)
    if started is None or skipped:
        return
    resolved_state = (state or "SUCCESS").upper()
    if failed or resolved_state == "FAILURE":
        if exception is None and isinstance(retval, BaseException):
            exception = retval
        outcome = RunOutcome(OUTCOME_FAILED, reason_from_exception(exception))
    elif resolved_state == "SUCCESS":
        outcome = outcome_from_result(retval)
    else:
        # RETRY, IGNORED, REJECTED: il giro non è finito, se ne scriverà un altro.
        return
    job_key, started_at, perf_start = started
    duration_ms = int((time.perf_counter() - perf_start) * 1000)
    _write_run(
        job_key=job_key,
        outcome=outcome,
        started_at=started_at,
        duration_ms=duration_ms,
        task_id=task_id,
    )


def _write_run(
    *,
    job_key: str,
    outcome: RunOutcome,
    started_at: datetime,
    duration_ms: int,
    task_id: str,
) -> None:
    try:
        from config.settings.loader import get_api_settings
        from database.session import create_engine_from_url, create_session_factory, session_scope

        settings = get_api_settings()
        engine = create_engine_from_url(settings.database_url)
        factory = create_session_factory(engine)
        try:
            with session_scope(factory) as session:
                record_run(
                    session,
                    job_key=job_key,
                    outcome=outcome.outcome,
                    reason=outcome.reason,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    duration_ms=duration_ms,
                    task_id=task_id,
                )
        finally:
            engine.dispose()
    except Exception:
        logger.exception("system_job_run_record_failed", extra={"job_key": job_key})
        return
    if outcome.outcome == OUTCOME_FAILED:
        logger.warning(
            f"system_job_run_failed job_key={job_key} reason={outcome.reason}",
            extra={"job_key": job_key},
        )
