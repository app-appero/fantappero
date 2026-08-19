"""Redis-backed rate limiting for auth endpoints."""

from __future__ import annotations

import hashlib
import logging

import redis

from auth.exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)


class AuthRateLimiter:
    """Fixed-window counters in Redis."""

    def __init__(self, redis_url: str) -> None:
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def check(self, *, endpoint: str, key: str, limit: int, window_seconds: int) -> None:
        redis_key = f"auth:rl:{endpoint}:{key}"
        try:
            count = self._client.incr(redis_key)
            if count == 1:
                self._client.expire(redis_key, window_seconds)
            if count > limit:
                raise RateLimitExceededError()
        except redis.RedisError:
            logger.warning(
                "auth_rate_limit_unavailable",
                extra={"endpoint": endpoint},
            )

    @staticmethod
    def email_key(email: str) -> str:
        normalized = email.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
