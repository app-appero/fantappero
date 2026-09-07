"""Redis-backed progress for async listone provider refresh jobs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import uuid4

import redis

from app.settings import redis_url
from observability.logging import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = "listone:refresh:job:"
_ACTIVE_KEY_PREFIX = "listone:refresh:active:"
_TTL_SECONDS = 60 * 60
_memory_store: dict[str, str] = {}
_ACTIVE_STATUSES = ("queued", "running")


@dataclass
class ListoneRefreshProgress:
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
    def from_dict(cls, payload: dict[str, Any]) -> ListoneRefreshProgress:
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
        logger.warning("listone_refresh_progress_redis_unavailable")
        return None


def save_progress(progress: ListoneRefreshProgress) -> None:
    """Persist progress and maintain the "active job for this scope" pointer.

    The pointer lets any client discover an in-progress refresh without
    already knowing its job_id — the only way another operator's session
    (that didn't start the job) can find out one is running (EP11-05).
    """
    payload = json.dumps(progress.to_dict())
    key = f"{_KEY_PREFIX}{progress.job_id}"
    active_key = f"{_ACTIVE_KEY_PREFIX}{progress.league_id}"
    is_active = progress.status in _ACTIVE_STATUSES
    client = _redis_client()
    if client is None:
        _memory_store[key] = payload
        if is_active:
            _memory_store[active_key] = progress.job_id
        else:
            _memory_store.pop(active_key, None)
        return
    client.setex(key, _TTL_SECONDS, payload)
    if is_active:
        client.setex(active_key, _TTL_SECONDS, progress.job_id)
    else:
        client.delete(active_key)


def load_progress(job_id: str) -> ListoneRefreshProgress | None:
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
        return ListoneRefreshProgress.from_dict(json.loads(raw))
    except (TypeError, ValueError, KeyError):
        return None


def load_active_job_id(league_id: str) -> str | None:
    """The job_id of the currently queued/running refresh for this scope, if any."""
    key = f"{_ACTIVE_KEY_PREFIX}{league_id}"
    client = _redis_client()
    if client is None:
        return _memory_store.get(key)
    value = client.get(key)
    return value if isinstance(value, str) else None


def clear_memory_store() -> None:
    """Test helper."""
    _memory_store.clear()
