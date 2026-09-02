"""Redis-backed progress for the async "Ricalcola storico" repair job.

Stessa struttura di `fantasy_turns.calendar_refresh_progress` ma con un
proprio prefisso di chiave Redis, per non condividere lo spazio job con il
refresh calendario (job diversi, stesso pattern infrastrutturale).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

import redis

from app.settings import redis_url
from observability.logging import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = "fantasy_turns:round_repair:job:"
_TTL_SECONDS = 60 * 60
_memory_store: dict[str, str] = {}


@dataclass
class RoundRepairProgress:
    job_id: str
    league_id: str
    status: str  # queued | running | completed | failed
    percent: int
    stage: str
    message: str
    error_code: str | None = None
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RoundRepairProgress:
        return cls(
            job_id=str(payload["job_id"]),
            league_id=str(payload["league_id"]),
            status=str(payload["status"]),
            percent=int(payload.get("percent") or 0),
            stage=str(payload.get("stage") or ""),
            message=str(payload.get("message") or ""),
            error_code=payload.get("error_code"),
            result=payload.get("result"),
        )


def new_job_id() -> str:
    return str(uuid4())


def _redis_client() -> redis.Redis | None:
    url = redis_url()
    if not url:
        return None
    try:
        client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        return client
    except Exception:
        logger.warning("round_repair_progress_redis_unavailable")
        return None


def save_progress(progress: RoundRepairProgress) -> None:
    payload = json.dumps(progress.to_dict())
    key = f"{_KEY_PREFIX}{progress.job_id}"
    client = _redis_client()
    if client is None:
        _memory_store[key] = payload
        return
    client.setex(key, _TTL_SECONDS, payload)


def load_progress(job_id: str) -> RoundRepairProgress | None:
    key = f"{_KEY_PREFIX}{job_id}"
    client = _redis_client()
    raw: str | None
    if client is None:
        raw = _memory_store.get(key)
    else:
        value = client.get(key)
        raw = value if isinstance(value, str) else None
    if not raw:
        return None
    try:
        return RoundRepairProgress.from_dict(json.loads(raw))
    except (TypeError, ValueError, KeyError):
        return None


def clear_memory_store() -> None:
    """Test helper."""
    _memory_store.clear()
