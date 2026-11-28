"""«In esecuzione» dei job: un segno su Redis per chiave, scritto da chi lancia e dal worker.

Serve a tre cose (release 1.5, «Esegui» del pannello operatore):

- non lanciare a mano un job che sta già girando (né due volte lo stesso lancio);
- sapere, dentro il task, che il giro è stato chiesto a mano da un operatore e quindi vale anche
  a job spento (``allow_periodic``);
- dire al pannello quali job girano in questo momento.

Il segno è ``SET NX EX`` (stessa idea di ``RedisJobLock`` dei giri sportivi) e scade da solo: se
il worker muore a metà, il job non resta bloccato per sempre. Il worker lo scrive all'inizio di
ogni giro del catalogo (segnale ``task_prerun``) e lo toglie alla fine (``task_postrun``), così
copre anche i giri partiti dal beat. Redis che non risponde non ferma mai un giro del worker; ferma
solo il lancio a mano (senza il segno non si può escludere il doppio lancio).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

import redis

from observability.logging import get_logger

logger = get_logger(__name__)

KEY_PREFIX = "fantappero:system_jobs:running:"
#: Un giro che non finisce (worker ucciso, deploy) libera il job dopo questo tempo.
RUNNING_TTL_SECONDS = 30 * 60

_RELEASE_LUA = """
local raw = redis.call("get", KEYS[1])
if not raw then
  return 0
end
local ok, data = pcall(cjson.decode, raw)
if ok and data["taskId"] == ARGV[1] then
  return redis.call("del", KEYS[1])
end
return 0
"""


class RunningUnavailableError(RuntimeError):
    """Redis non risponde: il lancio a mano non può escludere il doppio lancio."""


@dataclass(frozen=True)
class RunningMarker:
    task_id: str
    manual: bool
    actor_id: str | None
    started_at: str | None

    def to_json(self) -> str:
        return json.dumps(
            {
                "taskId": self.task_id,
                "manual": self.manual,
                "actorId": self.actor_id,
                "startedAt": self.started_at,
            }
        )

    @classmethod
    def from_json(cls, raw: str | bytes | None) -> RunningMarker | None:
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return cls(
                task_id=str(data["taskId"]),
                manual=bool(data.get("manual")),
                actor_id=data.get("actorId"),
                started_at=data.get("startedAt"),
            )
        except (ValueError, KeyError, TypeError):
            return None


def current_task_id() -> str | None:
    """Id del task Celery in corso (anche in modalità eager); ``None`` fuori da un task."""
    try:
        from celery import current_task

        if not current_task:
            return None
        task_id = getattr(current_task.request, "id", None)
    except Exception:  # noqa: BLE001 — fuori da un task non c'è niente da leggere
        return None
    return str(task_id) if task_id else None


def _key(job_key: str) -> str:
    return f"{KEY_PREFIX}{job_key}"


def _client() -> redis.Redis:
    from app.settings import redis_url

    url = redis_url()
    if not url:
        raise RunningUnavailableError("REDIS_URL non impostato.")
    return redis.Redis.from_url(
        url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
    )


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def claim(
    job_key: str,
    task_id: str,
    *,
    manual: bool,
    actor_id: str | None = None,
    ttl_seconds: int = RUNNING_TTL_SECONDS,
) -> RunningMarker | None:
    """Prenota il job: ``None`` se risulta già in esecuzione, altrimenti il segno scritto.

    Alza ``RunningUnavailableError`` se Redis non risponde: chi lancia a mano si ferma lì.
    """
    marker = RunningMarker(task_id, manual, actor_id, _now_iso())
    try:
        won = _client().set(_key(job_key), marker.to_json(), nx=True, ex=ttl_seconds)
    except redis.RedisError as exc:
        raise RunningUnavailableError(str(exc)) from exc
    return marker if won else None


def read(job_key: str) -> RunningMarker | None:
    try:
        return RunningMarker.from_json(_client().get(_key(job_key)))
    except (redis.RedisError, RunningUnavailableError):
        logger.warning("system_job_running_read_failed", extra={"job_key": job_key})
        return None


def read_many(job_keys: Iterable[str]) -> dict[str, RunningMarker]:
    """I job che girano adesso tra quelli indicati. Redis che non risponde = nessuno."""
    keys = list(dict.fromkeys(job_keys))
    if not keys:
        return {}
    try:
        values = _client().mget([_key(key) for key in keys])
    except (redis.RedisError, RunningUnavailableError):
        logger.warning("system_job_running_read_failed")
        return {}
    found: dict[str, RunningMarker] = {}
    for key, raw in zip(keys, values, strict=True):
        marker = RunningMarker.from_json(raw)
        if marker is not None:
            found[key] = marker
    return found


def release(job_key: str, task_id: str) -> bool:
    """Toglie il segno solo se è ancora di questo task (un altro giro non si cancella)."""
    try:
        return bool(_client().eval(_RELEASE_LUA, 1, _key(job_key), task_id))
    except (redis.RedisError, RunningUnavailableError):
        logger.warning("system_job_running_release_failed", extra={"job_key": job_key})
        return False


def mark_started_by_worker(job_key: str, task_id: str) -> None:
    """Inizio giro nel worker: tiene (o scrive) il segno di questo task. Mai un'eccezione."""
    try:
        client = _client()
        existing = RunningMarker.from_json(client.get(_key(job_key)))
        if existing is not None and existing.task_id == task_id:
            # Lancio a mano già prenotato dal pannello: resta com'è, si allunga solo la scadenza.
            client.expire(_key(job_key), RUNNING_TTL_SECONDS)
            return
        marker = RunningMarker(task_id, False, None, _now_iso())
        client.set(_key(job_key), marker.to_json(), ex=RUNNING_TTL_SECONDS)
    except (redis.RedisError, RunningUnavailableError):
        logger.warning("system_job_running_mark_failed", extra={"job_key": job_key})


def is_manual_run(job_key: str, task_id: str | None) -> bool:
    """Il giro in corso (``task_id``) è stato chiesto a mano dal pannello per questo job?"""
    if not task_id:
        return False
    marker = read(job_key)
    return marker is not None and marker.manual and marker.task_id == task_id


@contextmanager
def hold_jobs(job_keys: Iterable[str], token: str) -> Iterator[list[str]]:
    """Prenota più job per la durata del blocco; restituisce quelli già in esecuzione.

    Se anche uno solo è occupato non ne prenota nessuno (restituisce l'elenco degli occupati e
    chi chiama salta il lavoro). Redis che non risponde = niente prenotazione e nessun blocco:
    il lavoro parte comunque (è un'operazione dell'operatore già protetta da un altro blocco).
    """
    keys = list(dict.fromkeys(job_keys))
    taken: list[str] = []
    busy: list[str] = []
    try:
        for key in keys:
            try:
                marker = claim(key, token, manual=True)
            except RunningUnavailableError:
                logger.warning("system_job_running_unavailable", extra={"job_key": key})
                continue
            if marker is None:
                busy.append(key)
                continue
            taken.append(key)
        if busy:
            for key in taken:
                release(key, token)
            taken = []
        yield busy
    finally:
        for key in taken:
            release(key, token)
