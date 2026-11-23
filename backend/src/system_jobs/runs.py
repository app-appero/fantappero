"""Esito dei giri dei job periodici: scrittura, pulizia e lettura (release 1.4).

Prima ``system_jobs`` diceva solo quando un job era partito, non se era andato bene. Qui ogni
giro finito lascia una riga ``ok`` o ``failed`` con il motivo; il Riepilogo del pannello
operatore mostra i giri finiti con errore («Da guardare»).

La tabella resta piccola: per ogni job si tengono gli ultimi ``KEEP_RUNS_PER_JOB`` giri andati
bene e, al massimo per ``FAILED_RUNS_MAX_AGE``, gli ultimi ``KEEP_FAILED_RUNS_PER_JOB`` finiti
con errore (così un errore della notte non sparisce dietro i giri riusciti del mattino).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from sports_data.provider.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
)
from system_jobs.catalog import SYSTEM_JOBS, SYSTEM_JOBS_BY_KEY
from system_jobs.models import SystemJobRun

OUTCOME_OK = "ok"
OUTCOME_FAILED = "failed"
KEEP_RUNS_PER_JOB = 50
KEEP_FAILED_RUNS_PER_JOB = 100
FAILED_RUNS_MAX_AGE = timedelta(days=30)
REASON_MAX_LENGTH = 500

JOB_KEY_BY_TASK: dict[str, str] = {spec.task: spec.key for spec in SYSTEM_JOBS}


def job_key_for_task(task_name: str | None) -> str | None:
    """Chiave del job periodico eseguito da questo task Celery (None se non è un job del beat)."""
    if not task_name:
        return None
    return JOB_KEY_BY_TASK.get(task_name)


@dataclass(frozen=True)
class RunOutcome:
    outcome: str
    reason: str | None = None


def clip_reason(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = " ".join(str(text).split())
    if not cleaned:
        return None
    if len(cleaned) <= REASON_MAX_LENGTH:
        return cleaned
    return cleaned[: REASON_MAX_LENGTH - 1].rstrip() + "…"


def reason_from_exception(exc: BaseException | None) -> str:
    """Motivo leggibile di un giro finito con un'eccezione (con il tipo tecnico tra parentesi)."""
    if exc is None:
        return "Errore sconosciuto."
    name = type(exc).__name__
    if isinstance(exc, ProviderRateLimitError):
        return f"Fornitore sportivo: troppe richieste, limite raggiunto ({name})."
    if isinstance(exc, ProviderConfigError):
        return f"Fornitore sportivo: chiave mancante ({name})."
    if isinstance(exc, ProviderAuthError):
        return f"Fornitore sportivo: chiave non accettata ({name})."
    if isinstance(exc, ProviderError):
        return f"Fornitore sportivo non raggiungibile o risposta non valida ({name})."
    message = str(exc).strip()
    return clip_reason(f"{name}: {message}" if message else name) or name


def outcome_from_result(retval: object) -> RunOutcome:
    """Esito di un giro finito senza eccezioni.

    Alcuni job dicono «non riuscito» nel risultato invece di sollevare un'eccezione:
    ``{"status": "failed" | "error", "code" | "error_code": …}`` oppure, per il giro del
    calendario di tutte le leghe, ``{"failed": N, "leagues": M}`` con N leghe non aggiornate.
    """
    if not isinstance(retval, dict):
        return RunOutcome(OUTCOME_OK)
    status = retval.get("status")
    if isinstance(status, str) and status.strip().lower() in {"failed", "error"}:
        detail = next(
            (
                str(retval[key])
                for key in ("error_code", "code", "message")
                if isinstance(retval.get(key), str) and str(retval[key]).strip()
            ),
            None,
        )
        reason = f"Il giro dice «{status}»" + (f": {detail}." if detail else ".")
        return RunOutcome(OUTCOME_FAILED, clip_reason(reason))
    failed = retval.get("failed")
    if isinstance(failed, int) and not isinstance(failed, bool) and failed > 0:
        total = retval.get("leagues")
        if isinstance(total, int) and not isinstance(total, bool) and total >= failed:
            reason = f"Non riuscito per {failed} leghe su {total}."
        else:
            reason = f"Non riuscito per {failed} elementi."
        return RunOutcome(OUTCOME_FAILED, reason)
    return RunOutcome(OUTCOME_OK)


def record_run(
    session: Session,
    *,
    job_key: str,
    outcome: str,
    started_at: datetime,
    finished_at: datetime,
    reason: str | None = None,
    task_id: str | None = None,
    duration_ms: int | None = None,
) -> SystemJobRun:
    """Scrive l'esito di un giro e poi pulisce le righe vecchie di quel job."""
    if outcome not in (OUTCOME_OK, OUTCOME_FAILED):
        raise ValueError(f"esito sconosciuto: {outcome}")
    row = SystemJobRun(
        job_key=job_key,
        task_id=(task_id or None) and task_id[:64],
        outcome=outcome,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        reason=clip_reason(reason) if outcome == OUTCOME_FAILED else None,
    )
    session.add(row)
    session.flush()
    prune_runs(session, job_key=job_key, now=finished_at)
    return row


def prune_runs(session: Session, *, job_key: str, now: datetime) -> None:
    keep_ok = (
        select(SystemJobRun.id)
        .where(SystemJobRun.job_key == job_key, SystemJobRun.outcome == OUTCOME_OK)
        .order_by(SystemJobRun.started_at.desc(), SystemJobRun.id.desc())
        .limit(KEEP_RUNS_PER_JOB)
    )
    keep_failed = (
        select(SystemJobRun.id)
        .where(SystemJobRun.job_key == job_key, SystemJobRun.outcome == OUTCOME_FAILED)
        .order_by(SystemJobRun.started_at.desc(), SystemJobRun.id.desc())
        .limit(KEEP_FAILED_RUNS_PER_JOB)
    )
    session.execute(
        delete(SystemJobRun)
        .where(
            SystemJobRun.job_key == job_key,
            or_(
                and_(
                    SystemJobRun.outcome == OUTCOME_OK,
                    SystemJobRun.id.not_in(keep_ok.scalar_subquery()),
                ),
                and_(
                    SystemJobRun.outcome == OUTCOME_FAILED,
                    or_(
                        SystemJobRun.started_at < now - FAILED_RUNS_MAX_AGE,
                        SystemJobRun.id.not_in(keep_failed.scalar_subquery()),
                    ),
                ),
            ),
        )
        .execution_options(synchronize_session=False)
    )


@dataclass(frozen=True)
class JobFailureView:
    """Un job con almeno un giro finito con errore nel periodo guardato."""

    job_key: str
    title: str
    failed_at: datetime
    reason: str | None
    failures: int
    #: Esito dell'ultimo giro del job, anche se successivo all'errore: ``ok`` = già ripreso.
    last_outcome: str
    last_finished_at: datetime


def recent_failures(session: Session, *, since: datetime) -> list[JobFailureView]:
    """Job con giri finiti con errore da ``since``: il più recente per primo."""
    failed_rows = session.scalars(
        select(SystemJobRun)
        .where(SystemJobRun.outcome == OUTCOME_FAILED, SystemJobRun.started_at >= since)
        .order_by(SystemJobRun.started_at.desc(), SystemJobRun.id.desc())
    ).all()
    latest_failed: dict[str, SystemJobRun] = {}
    counts: dict[str, int] = {}
    for row in failed_rows:
        latest_failed.setdefault(row.job_key, row)
        counts[row.job_key] = counts.get(row.job_key, 0) + 1
    if not latest_failed:
        return []
    last_runs = latest_runs(session, job_keys=latest_failed.keys())
    views: list[JobFailureView] = []
    for key, row in latest_failed.items():
        spec = SYSTEM_JOBS_BY_KEY.get(key)
        last = last_runs.get(key, row)
        views.append(
            JobFailureView(
                job_key=key,
                title=spec.title if spec is not None else key,
                failed_at=row.finished_at,
                reason=row.reason,
                failures=counts[key],
                last_outcome=last.outcome,
                last_finished_at=last.finished_at,
            )
        )
    views.sort(key=lambda view: view.failed_at, reverse=True)
    return views


def latest_runs(session: Session, *, job_keys: Iterable[str]) -> dict[str, SystemJobRun]:
    """Ultimo giro di ciascun job indicato."""
    keys = list(dict.fromkeys(job_keys))
    if not keys:
        return {}
    rows = session.scalars(
        select(SystemJobRun)
        .where(SystemJobRun.job_key.in_(keys))
        .distinct(SystemJobRun.job_key)
        .order_by(SystemJobRun.job_key, SystemJobRun.started_at.desc(), SystemJobRun.id.desc())
    ).all()
    return {row.job_key: row for row in rows}
