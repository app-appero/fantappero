"""Fixed-window rate limiting for auth endpoints."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)


class RateLimiter(Protocol):
    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Return True when the attempt is allowed, False when limited."""


@dataclass
class MemoryRateLimiter:
    """In-process limiter for tests and environments without Redis."""

    _counts: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.time()
        window_start = now - window_seconds
        attempts = [stamp for stamp in self._counts[key] if stamp >= window_start]
        if len(attempts) >= limit:
            self._counts[key] = attempts
            return False
        attempts.append(now)
        self._counts[key] = attempts
        return True


class RedisRateLimiter:
    """Redis-backed fixed window counter."""

    def __init__(self, redis_url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def hit(self, key: str, *, limit: int, window_seconds: int) -> bool:
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds, nx=True)
        count, _ = pipe.execute()
        return int(count) <= limit


def create_rate_limiter(redis_url: str | None) -> RateLimiter:
    if not redis_url:
        logger.info("auth.rate_limiter using in-memory backend")
        return MemoryRateLimiter()
    try:
        return RedisRateLimiter(redis_url)
    except Exception:
        logger.exception("auth.rate_limiter redis unavailable; falling back to memory")
        return MemoryRateLimiter()
