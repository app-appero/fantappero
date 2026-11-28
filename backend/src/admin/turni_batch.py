"""«Esegui tutti» nel pannello operatore › Turni (release 1.5).

Lancia in sequenza le operazioni dei turni che si possono rilanciare senza danni, una dopo
l'altra, in un task Celery (``admin.run_turni_batch``): un errore non ferma le altre e ogni
operazione lascia il suo esito (ok, non riuscita con il messaggio, saltata).

Le operazioni sono quelle dei pulsanti «Azioni massive», con la stessa logica:

1. ``importa-stagione``      Importa calendario stagione (catalogo e partite di tutti i campionati);
2. ``genera-calendario``     Genera calendario (riallinea partite e turni di ogni lega attiva);
3. ``sincronizza-turni``     Sincronizza turni (apre i turni pronti, ricalcola i cutoff);
4. ``formazioni-probabili``  Aggiorna probabili (formazioni probabili, anche se recenti);
5. ``formazioni-ia``         Genera formazioni IA (solo squadre IA, mai quelle dei fantallenatori).

Restano fuori, apposta, le azioni a senso unico o che toccano lo storico: «Calcola giornata
corrente» e «Recupera risultati» (omologano i turni), «Ricalcola storico» (riapre turni già
omologati, avvisa gli utenti e vuole un motivo) e le azioni per singola lega o turno.

Doppio lancio: un solo blocco alla volta (chiave Redis ``SET NX``, scade da solo) e ogni
operazione prenota i job automatici che fanno la stessa cosa (``system_jobs.running``): se uno sta
girando, l'operazione si salta con un messaggio chiaro invece di partire due volte.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import redis

from observability.logging import get_logger

logger = get_logger(__name__)

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

OP_PENDING = "pending"
OP_RUNNING = "running"
OP_OK = "ok"
OP_FAILED = "failed"
OP_SKIPPED = "skipped"

AUDIT_OPERATION_BATCH = "turni_batch_manual_run"
RUN_BATCH_TASK = "admin.run_turni_batch"

_LOCK_KEY = "fantappero:admin:turni_batch:lock"
_PROGRESS_PREFIX = "fantappero:admin:turni_batch:progress:"
#: Il blocco scade da solo se il worker muore a metà: dopo questo tempo si può rilanciare.
LOCK_TTL_SECONDS = 60 * 60
PROGRESS_TTL_SECONDS = 2 * 60 * 60

_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
end
return 0
"""


class BatchUnavailableError(RuntimeError):
    """Redis non risponde: senza blocco non si può escludere il doppio lancio."""


class OperationFailedError(Exception):
    """Operazione non riuscita con un messaggio già pronto per l'operatore."""


@dataclass(frozen=True)
class BatchOperationSpec:
    key: str
    label: str
    #: Job automatici che fanno la stessa cosa: se uno gira, l'operazione si salta.
    job_keys: tuple[str, ...] = ()


#: L'ordine è quello di esecuzione: dati dal fornitore → calendario → turni → formazioni.
BATCH_OPERATIONS: tuple[BatchOperationSpec, ...] = (
    BatchOperationSpec(
        "importa-stagione",
        "Importa calendario stagione",
        ("sports-data-sync-catalog", "sports-data-sync-fixtures"),
    ),
    BatchOperationSpec(
        "genera-calendario",
        "Genera calendario",
        ("fantasy-turns-refresh-full-calendar",),
    ),
    BatchOperationSpec(
        "sincronizza-turni",
        "Sincronizza turni",
        ("fantasy-turns-ensure-upcoming",),
    ),
    BatchOperationSpec(
        "formazioni-probabili",
        "Aggiorna probabili",
        ("sports-predicted-lineups",),
    ),
    BatchOperationSpec(
        "formazioni-ia",
        "Genera formazioni IA",
        ("fantasy-lineups-generate-ai",),
    ),
)
BATCH_OPERATIONS_BY_KEY = {spec.key: spec for spec in BATCH_OPERATIONS}


@dataclass
class BatchOperation:
    key: str
    label: str
    status: str = OP_PENDING
    message: str | None = None


@dataclass
class BatchProgress:
    batch_id: str
    actor_id: str
    status: str = STATUS_QUEUED
    operations: list[BatchOperation] = field(default_factory=list)
    started_at: str | None = None
    finished_at: str | None = None

    def count(self, status: str) -> int:
        return sum(1 for operation in self.operations if operation.status == status)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BatchProgress:
        return cls(
            batch_id=str(payload["batch_id"]),
            actor_id=str(payload.get("actor_id") or ""),
            status=str(payload.get("status") or STATUS_QUEUED),
            operations=[
                BatchOperation(
                    key=str(item["key"]),
                    label=str(item["label"]),
                    status=str(item.get("status") or OP_PENDING),
                    message=item.get("message"),
                )
                for item in payload.get("operations", [])
            ],
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
        )


def new_batch_id() -> str:
    return str(uuid4())


def new_progress(batch_id: str, actor_id: str) -> BatchProgress:
    return BatchProgress(
        batch_id=batch_id,
        actor_id=actor_id,
        operations=[BatchOperation(spec.key, spec.label) for spec in BATCH_OPERATIONS],
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _client() -> redis.Redis:
    from app.settings import redis_url

    url = redis_url()
    if not url:
        raise BatchUnavailableError("REDIS_URL non impostato.")
    return redis.Redis.from_url(
        url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
    )


def acquire_lock(batch_id: str) -> bool:
    """Prenota «un solo blocco alla volta». False se un altro blocco sta girando."""
    try:
        return bool(_client().set(_LOCK_KEY, batch_id, nx=True, ex=LOCK_TTL_SECONDS))
    except redis.RedisError as exc:
        raise BatchUnavailableError(str(exc)) from exc


def release_lock(batch_id: str) -> None:
    try:
        _client().eval(_RELEASE_LUA, 1, _LOCK_KEY, batch_id)
    except (redis.RedisError, BatchUnavailableError):
        logger.warning("turni_batch_lock_release_failed", extra={"batch_id": batch_id})


def save_progress(progress: BatchProgress) -> None:
    try:
        _client().setex(
            f"{_PROGRESS_PREFIX}{progress.batch_id}",
            PROGRESS_TTL_SECONDS,
            json.dumps(progress.to_dict()),
        )
    except (redis.RedisError, BatchUnavailableError):
        logger.warning("turni_batch_progress_save_failed", extra={"batch_id": progress.batch_id})


def load_progress(batch_id: str) -> BatchProgress | None:
    try:
        raw = _client().get(f"{_PROGRESS_PREFIX}{batch_id}")
    except (redis.RedisError, BatchUnavailableError):
        logger.warning("turni_batch_progress_load_failed", extra={"batch_id": batch_id})
        return None
    if not raw:
        return None
    try:
        return BatchProgress.from_dict(json.loads(raw))
    except (ValueError, KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Operazioni
# ---------------------------------------------------------------------------


def _progress_message(job_id: str, outcome: object) -> str:
    """Messaggio di un'operazione che pubblica l'avanzamento nello store del calendario."""
    from fantasy_turns.calendar_refresh_progress import load_progress as load_calendar_progress

    progress = load_calendar_progress(job_id)
    if progress is None:
        if isinstance(outcome, dict) and outcome.get("status") == "failed":
            raise OperationFailedError(f"Non riuscita ({outcome.get('code') or 'errore'}).")
        return "Completata."
    if progress.status == "failed":
        raise OperationFailedError(progress.message or "Non riuscita.")
    failed = (progress.result or {}).get("failed")
    if isinstance(failed, int) and not isinstance(failed, bool) and failed > 0:
        raise OperationFailedError(progress.message)
    return progress.message or "Completata."


def _run_import_season(actor_id: str) -> str:
    from fantasy_turns.calendar_refresh_progress import new_job_id
    from sports_data.season_import_tasks import import_season_task

    job_id = new_job_id()
    outcome = import_season_task(job_id=job_id, actor_id=actor_id)
    return _progress_message(job_id, outcome)


def _run_generate_calendar(actor_id: str) -> str:
    from fantasy_turns.calendar_refresh_progress import new_job_id
    from fantasy_turns.tasks import refresh_full_calendar_active_leagues_now_task

    job_id = new_job_id()
    outcome = refresh_full_calendar_active_leagues_now_task(job_id=job_id, actor_id=actor_id)
    return _progress_message(job_id, outcome)


def _run_sync_turns(actor_id: str) -> str:
    from config.settings.loader import get_api_settings
    from database.session import create_engine_from_url, create_session_factory, session_scope
    from fantasy_turns.service import FantasyTurnService

    engine = create_engine_from_url(get_api_settings().database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            totals = FantasyTurnService(session).ensure_upcoming_for_active_leagues()
    finally:
        engine.dispose()
    return (
        f"Leghe: {totals['leagues']}. Turni creati: {totals['created']}, aperti: "
        f"{totals['opened']}, aggiornati: {totals['upgraded']}, in attesa: {totals['waiting']}."
    )


def _run_predicted_lineups(actor_id: str) -> str:
    from sports_data.predicted.tasks import run_predicted_lineup_sync

    payload = run_predicted_lineup_sync(force=True, manual=True)
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message
    return (
        f"Formazioni probabili aggiornate: {int(payload.get('snapshots_saved') or 0)} salvate, "
        f"{int(payload.get('skipped_unmatched') or 0)} senza corrispondenza."
    )


def _run_ai_lineups(actor_id: str) -> str:
    from config.settings.loader import get_api_settings
    from database.session import create_engine_from_url, create_session_factory, session_scope
    from fantasy_lineups.ai_service import generate_ai_lineups_for_active_leagues

    engine = create_engine_from_url(get_api_settings().database_url)
    try:
        with session_scope(create_session_factory(engine)) as session:
            result = generate_ai_lineups_for_active_leagues(session)
    finally:
        engine.dispose()
    return (
        f"Turni processati: {result['rounds']}. Squadre aggiornate: {result['teamsUpdated']}, "
        f"invariate: {result['teamsSkipped']}."
    )


#: Chi esegue ogni operazione: ``(actor_id) -> messaggio``. I test li sostituiscono con finti.
OPERATION_RUNNERS: dict[str, Callable[[str], str]] = {
    "importa-stagione": _run_import_season,
    "genera-calendario": _run_generate_calendar,
    "sincronizza-turni": _run_sync_turns,
    "formazioni-probabili": _run_predicted_lineups,
    "formazioni-ia": _run_ai_lineups,
}


def _failure_message(exc: BaseException) -> str:
    if isinstance(exc, OperationFailedError):
        return str(exc) or "Non riuscita."
    from system_jobs.runs import reason_from_exception

    return f"Non riuscita: {reason_from_exception(exc)}"


def _run_operation(spec: BatchOperationSpec, operation: BatchOperation, actor_id: str) -> None:
    from system_jobs.running import hold_jobs

    token = f"turni-batch:{spec.key}:{uuid4()}"
    with hold_jobs(spec.job_keys, token) as busy:
        if busy:
            operation.status = OP_SKIPPED
            operation.message = (
                "Saltata: il job automatico che fa la stessa cosa è già in esecuzione "
                "(ritenta fra poco)."
            )
            return
        try:
            operation.message = OPERATION_RUNNERS[spec.key](actor_id)
            operation.status = OP_OK
        except Exception as exc:  # noqa: BLE001 — un errore non deve fermare le altre operazioni
            logger.exception(f"turni_batch_operation_failed operation={spec.key}")
            operation.status = OP_FAILED
            operation.message = _failure_message(exc)


def run_batch(batch_id: str, actor_id: str) -> BatchProgress:
    """Esegue le operazioni in sequenza e pubblica l'avanzamento dopo ognuna."""
    progress = load_progress(batch_id) or new_progress(batch_id, actor_id)
    progress.status = STATUS_RUNNING
    progress.started_at = progress.started_at or _now_iso()
    save_progress(progress)
    try:
        for operation in progress.operations:
            spec = BATCH_OPERATIONS_BY_KEY[operation.key]
            operation.status = OP_RUNNING
            save_progress(progress)
            _run_operation(spec, operation, actor_id)
            save_progress(progress)
        progress.status = STATUS_COMPLETED
    except BaseException:
        progress.status = STATUS_FAILED
        for operation in progress.operations:
            if operation.status in (OP_PENDING, OP_RUNNING):
                operation.status = OP_FAILED
                operation.message = "Interrotta: il blocco si è fermato prima di finire."
        raise
    finally:
        progress.finished_at = _now_iso()
        save_progress(progress)
        release_lock(batch_id)
    return progress
