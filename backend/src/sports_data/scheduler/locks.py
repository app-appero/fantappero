"""Distributed job locks for sports poll tasks (EP04-06)."""

from __future__ import annotations

import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

import redis

from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.provider.constants import PROVIDER_NAME

logger = get_logger(__name__)

SCHEDULER_LOCK_ACQUIRED_TOTAL = "sports_scheduler_lock_acquired_total"
SCHEDULER_LOCK_SKIPPED_TOTAL = "sports_scheduler_lock_skipped_total"
SCHEDULER_LOCK_ERRORS_TOTAL = "sports_scheduler_lock_errors_total"

_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
end
return 0
"""


class JobLock(Protocol):
    def try_acquire(self, name: str, *, ttl_seconds: int) -> str | None: ...

    def release(self, name: str, token: str) -> bool: ...


@dataclass
class InMemoryJobLock:
    """Process-local lock for unit tests (not multi-worker safe)."""

    _entries: dict[str, tuple[str, float]]

    def __init__(self) -> None:
        self._entries = {}

    def try_acquire(self, name: str, *, ttl_seconds: int) -> str | None:
        now = time.monotonic()
        existing = self._entries.get(name)
        if existing is not None and existing[1] > now:
            return None
        token = secrets.token_hex(16)
        self._entries[name] = (token, now + max(1, ttl_seconds))
        return token

    def release(self, name: str, token: str) -> bool:
        existing = self._entries.get(name)
        if existing is None or existing[0] != token:
            return False
        del self._entries[name]
        return True


class RedisJobLock:
    """Redis SET NX EX lease — prevents concurrent duplicate poll jobs."""

    def __init__(self, redis_url: str, *, key_prefix: str = "sports:poll:lock:") -> None:
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._prefix = key_prefix

    def try_acquire(self, name: str, *, ttl_seconds: int) -> str | None:
        key = f"{self._prefix}{name}"
        token = secrets.token_hex(16)
        metrics = get_metrics()
        labels = {"provider": PROVIDER_NAME, "lock": name}
        try:
            ok = self._client.set(key, token, nx=True, ex=max(1, int(ttl_seconds)))
        except redis.RedisError:
            metrics.incr(SCHEDULER_LOCK_ERRORS_TOTAL, labels=labels)
            logger.warning(
                "sports_scheduler_lock_error",
                extra={"provider": PROVIDER_NAME, "lock": name, "op": "acquire"},
            )
            return None
        if ok:
            metrics.incr(SCHEDULER_LOCK_ACQUIRED_TOTAL, labels=labels)
            return token
        metrics.incr(SCHEDULER_LOCK_SKIPPED_TOTAL, labels=labels)
        logger.info(
            "sports_scheduler_lock_busy",
            extra={"provider": PROVIDER_NAME, "lock": name},
        )
        return None

    def release(self, name: str, token: str) -> bool:
        key = f"{self._prefix}{name}"
        try:
            result = self._client.eval(_RELEASE_LUA, 1, key, token)
            return bool(result)
        except redis.RedisError:
            get_metrics().incr(
                SCHEDULER_LOCK_ERRORS_TOTAL,
                labels={"provider": PROVIDER_NAME, "lock": name},
            )
            logger.warning(
                "sports_scheduler_lock_error",
                extra={"provider": PROVIDER_NAME, "lock": name, "op": "release"},
            )
            return False


@contextmanager
def hold_job_lock(
    lock: JobLock,
    name: str,
    *,
    ttl_seconds: int,
) -> Iterator[str | None]:
    """Acquire a lock for the duration of the block; yield None if busy."""
    token = lock.try_acquire(name, ttl_seconds=ttl_seconds)
    try:
        yield token
    finally:
        if token is not None:
            lock.release(name, token)
