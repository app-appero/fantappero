"""Lancio a mano dei job dal pannello operatore: «Esegui» e «Esegui tutti» (release 1.5).

Il lancio manda al worker lo stesso task Celery che manda il beat (``spec.task`` con i suoi
``kwargs`` di catalogo), non esegue niente dentro la richiesta HTTP. Le frequenze e gli orari
del beat non cambiano.

- **Doppio lancio.** Prima di mandare il task il job si prenota su Redis (``system_jobs.running``,
  ``SET NX``): se risulta già in esecuzione (lancio a mano o giro del beat) non si rilancia. Il
  worker toglie il segno a fine giro; se muore, il segno scade da solo.
- **Job spento.** Si può lanciare a mano: il segno dice al task che il giro è stato chiesto da un
  operatore e ``allow_periodic`` lo lascia passare una volta sola. Il risultato porta un avviso.
- **Chi e quando.** Ogni lancio andato a buon fine scrive una riga di audit di piattaforma
  (``LeagueAuditEvent``, ``league_id`` nullo, azione ``system_job_run_manual``) e una riga di log.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import LeagueAuditAction
from leagues.models.league_audit_event import LeagueAuditEvent
from observability.logging import get_logger
from system_jobs.catalog import SYSTEM_JOBS, SYSTEM_JOBS_BY_KEY, SystemJobSpec
from system_jobs.models import SystemJob
from system_jobs.running import RunningUnavailableError, claim, release
from system_jobs.service import ensure_defaults

logger = get_logger(__name__)

STATUS_STARTED = "started"
STATUS_ALREADY_RUNNING = "already_running"
STATUS_FAILED = "failed"

CODE_ALREADY_RUNNING = "system_job_already_running"
CODE_LOCK_UNAVAILABLE = "system_job_lock_unavailable"
CODE_DISPATCH_FAILED = "system_job_dispatch_failed"

AUDIT_OPERATION_JOB = "system_job_manual_run"


@dataclass(frozen=True)
class ManualRunResult:
    key: str
    title: str
    #: ``started`` (task in coda), ``already_running`` (non rilanciato) o ``failed``.
    status: str
    message: str
    warning: str | None = None
    code: str | None = None
    task_id: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "title": self.title,
            "status": self.status,
            "message": self.message,
            "warning": self.warning,
            "code": self.code,
            "taskId": self.task_id,
        }


def dispatch_task(task_name: str, *, task_id: str, kwargs: dict[str, object]) -> None:
    """Manda il task al worker (in ambiente di test Celery lo esegue subito, modalità eager)."""
    from app.worker import celery_app

    celery_app.tasks[task_name].apply_async(kwargs=kwargs, task_id=task_id)


def launch_job(session: Session, key: str, *, actor_id: UUID) -> ManualRunResult:
    """«Esegui» su un job. Alza ``ValidationAuthError`` (404) solo se la chiave non esiste."""
    spec = SYSTEM_JOBS_BY_KEY.get(key)
    if spec is None:
        raise ValidationAuthError("Job sconosciuto.", code="system_job_not_found")
    ensure_defaults(session)
    row = session.get(SystemJob, key)
    if row is None:
        raise ValidationAuthError("Job sconosciuto.", code="system_job_not_found")
    return _launch(session, spec, enabled=row.enabled, actor_id=actor_id, batch=False)


def launch_all_enabled(session: Session, *, actor_id: UUID) -> list[ManualRunResult]:
    """«Esegui tutti»: un lancio per ogni job acceso, nell'ordine del catalogo.

    Un job che fallisce o che sta già girando non ferma gli altri. I job spenti non si toccano.
    """
    ensure_defaults(session)
    enabled = {row.key for row in session.scalars(select(SystemJob)).all() if row.enabled}
    results: list[ManualRunResult] = []
    for spec in SYSTEM_JOBS:
        if spec.key in enabled:
            results.append(_launch(session, spec, enabled=True, actor_id=actor_id, batch=True))
    return results


def _launch(
    session: Session,
    spec: SystemJobSpec,
    *,
    enabled: bool,
    actor_id: UUID,
    batch: bool,
) -> ManualRunResult:
    task_id = str(uuid4())
    try:
        marker = claim(spec.key, task_id, manual=True, actor_id=str(actor_id))
    except RunningUnavailableError:
        logger.warning(f"system_job_manual_run_lock_unavailable job_key={spec.key}")
        return ManualRunResult(
            key=spec.key,
            title=spec.title,
            status=STATUS_FAILED,
            code=CODE_LOCK_UNAVAILABLE,
            message=(
                f"«{spec.title}» non lanciato: non riesco a controllare se sta già girando "
                "(Redis non risponde). Riprova tra poco."
            ),
        )
    if marker is None:
        return ManualRunResult(
            key=spec.key,
            title=spec.title,
            status=STATUS_ALREADY_RUNNING,
            code=CODE_ALREADY_RUNNING,
            message=f"«{spec.title}» è già in esecuzione: non lo rilancio.",
        )
    try:
        dispatch_task(spec.task, task_id=task_id, kwargs=dict(spec.kwargs))
    except Exception as exc:  # noqa: BLE001 — il broker o il worker non rispondono
        release(spec.key, task_id)
        logger.exception(f"system_job_manual_run_dispatch_failed job_key={spec.key}")
        return ManualRunResult(
            key=spec.key,
            title=spec.title,
            status=STATUS_FAILED,
            code=CODE_DISPATCH_FAILED,
            message=(
                f"«{spec.title}» non lanciato: non riesco a metterlo in coda "
                f"({type(exc).__name__})."
            ),
        )
    session.add(
        LeagueAuditEvent(
            league_id=None,
            actor_id=actor_id,
            action=LeagueAuditAction.SYSTEM_JOB_RUN_MANUAL,
            details={
                "operation": AUDIT_OPERATION_JOB,
                "jobKey": spec.key,
                "taskId": task_id,
                "wasEnabled": enabled,
                "allJobs": batch,
            },
        )
    )
    session.flush()
    logger.info(
        f"system_job_manual_run_started job_key={spec.key} actor_id={actor_id} "
        f"task_id={task_id} was_enabled={enabled}",
        extra={"job_key": spec.key, "actor_id": str(actor_id), "task_id": task_id},
    )
    warning = (
        None
        if enabled
        else (f"«{spec.title}» è spento: l'ho lanciato a mano una volta sola, non riparte da solo.")
    )
    return ManualRunResult(
        key=spec.key,
        title=spec.title,
        status=STATUS_STARTED,
        message=f"«{spec.title}» lanciato: il giro è in coda e parte tra poco.",
        warning=warning,
        task_id=task_id,
    )
