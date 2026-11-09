"""Redis-backed rate limiting for auth endpoints."""

from __future__ import annotations

import hashlib
import logging
import time

import redis

from auth.exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)

#: Login attempts on one account before the growing wait kicks in. Below this,
#: a normal person mistyping their password is never slowed down.
_LOGIN_BACKOFF_FREE_ATTEMPTS = 5
#: Required wait before the next attempt, one entry per failure past the free
#: ones; the last value repeats for every failure beyond it (capped, not unbounded).
_LOGIN_BACKOFF_SCHEDULE_SECONDS = (30, 120, 600)
#: The failure counter forgets itself if nobody retries for this long.
_LOGIN_BACKOFF_RESET_SECONDS = 3600


class AuthRateLimiter:
    """Fixed-window counters in Redis, plus a per-account login backoff."""

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

    def check_login_backoff(self, email: str) -> None:
        """Reject a login attempt still inside the wait earned by recent failures on this account.

        Per-account, on top of the per-IP window in ``check``: an attacker spreading guesses
        across many IPs (or a slow, patient one) never trips the IP limit but would otherwise
        get unlimited tries against a single account. Keyed by the email regardless of whether
        the account exists, and with the same generic error either way, so the timing never
        tells an attacker an account is real before `InvalidCredentialsError` would.
        """
        redis_key = f"auth:login_backoff:{self.email_key(email)}"
        try:
            raw = self._client.hgetall(redis_key)
        except redis.RedisError:
            logger.warning("auth_rate_limit_unavailable", extra={"endpoint": "login_backoff"})
            return
        if not raw:
            return
        count = int(raw.get("count", 0))
        last_failure_at = float(raw.get("last_failure_at", 0))
        wait_seconds = self._login_backoff_wait_seconds(count)
        if wait_seconds <= 0:
            return
        if time.time() - last_failure_at < wait_seconds:
            raise RateLimitExceededError()

    def record_login_failure(self, email: str) -> None:
        redis_key = f"auth:login_backoff:{self.email_key(email)}"
        try:
            with self._client.pipeline() as pipe:
                pipe.hincrby(redis_key, "count", 1)
                pipe.hset(redis_key, "last_failure_at", time.time())
                pipe.expire(redis_key, _LOGIN_BACKOFF_RESET_SECONDS)
                pipe.execute()
        except redis.RedisError:
            logger.warning("auth_rate_limit_unavailable", extra={"endpoint": "login_backoff"})

    def record_login_success(self, email: str) -> None:
        redis_key = f"auth:login_backoff:{self.email_key(email)}"
        try:
            self._client.delete(redis_key)
        except redis.RedisError:
            logger.warning("auth_rate_limit_unavailable", extra={"endpoint": "login_backoff"})

    @staticmethod
    def _login_backoff_wait_seconds(count: int) -> int:
        extra_failures = count - _LOGIN_BACKOFF_FREE_ATTEMPTS
        if extra_failures <= 0:
            return 0
        index = min(extra_failures - 1, len(_LOGIN_BACKOFF_SCHEDULE_SECONDS) - 1)
        return _LOGIN_BACKOFF_SCHEDULE_SECONDS[index]

    @staticmethod
    def email_key(email: str) -> str:
        normalized = email.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
