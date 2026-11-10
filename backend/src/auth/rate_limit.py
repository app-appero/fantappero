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

#: KEYS[1] = the account's hash key.
#: ARGV[1] = free attempts, ARGV[2] = reset TTL seconds, ARGV[3] = now (unix time),
#: ARGV[4..] = the wait schedule, in order, capped at the last entry.
#: Reads the counter and treats *this* attempt as the one being reserved (so "free
#: attempts" also covers the one making the request), only mutating state when it is
#: actually allowed through — a call made while still inside the wait leaves the
#: counter and timestamp untouched, so repeated polling against a blocked account
#: never pushes it into a longer tier on its own.
_LOGIN_BACKOFF_SCRIPT = """
local key = KEYS[1]
local free_attempts = tonumber(ARGV[1])
local reset_seconds = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local schedule_len = #ARGV - 3

local count = tonumber(redis.call('HGET', key, 'count') or '0')
local last_at = tonumber(redis.call('HGET', key, 'last_failure_at') or '0')

local extra = (count + 1) - free_attempts
local wait = 0
if extra > 0 then
    local idx = extra
    if idx > schedule_len then idx = schedule_len end
    wait = tonumber(ARGV[3 + idx])
end

local elapsed = now - last_at
if wait > 0 and elapsed < wait then
    return tostring(wait - elapsed)
end

redis.call('HINCRBY', key, 'count', 1)
redis.call('HSET', key, 'last_failure_at', now)
redis.call('EXPIRE', key, reset_seconds)
return '0'
"""


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
        """Reject a login attempt still inside the wait earned by recent attempts on this
        account, and otherwise atomically reserve this one as the next attempt.

        Per-account, on top of the per-IP window in ``check``: an attacker spreading guesses
        across many IPs (or a slow, patient one) never trips the IP limit but would otherwise
        get unlimited tries against a single account. Keyed by the email regardless of whether
        the account exists, and with the same generic error either way, so the timing never
        tells an attacker an account is real before `InvalidCredentialsError` would.

        The check and the reservation used to be two separate Redis round trips (read the
        counter here, increment it later in ``record_login_failure`` once the password turned
        out wrong) — a burst of concurrent requests for the same account would all read the
        same low counter before any of them got around to recording a failure, sailing straight
        through the backoff it exists to stop. A single Lua script run inside Redis closes that
        gap: this account's counter and wait decision happen as one atomic step, so even a
        flood of simultaneous attempts gets serialized against it one at a time. A blocked
        attempt here never got to try a password, so it leaves the counter untouched; only a
        reserved one does — undone on an eventual successful login via ``record_login_success``.
        """
        redis_key = f"auth:login_backoff:{self.email_key(email)}"
        try:
            remaining = self._client.eval(
                _LOGIN_BACKOFF_SCRIPT,
                1,
                redis_key,
                _LOGIN_BACKOFF_FREE_ATTEMPTS,
                _LOGIN_BACKOFF_RESET_SECONDS,
                time.time(),
                *_LOGIN_BACKOFF_SCHEDULE_SECONDS,
            )
        except redis.RedisError:
            logger.warning("auth_rate_limit_unavailable", extra={"endpoint": "login_backoff"})
            return
        if float(remaining) > 0:
            raise RateLimitExceededError()

    def record_login_success(self, email: str) -> None:
        redis_key = f"auth:login_backoff:{self.email_key(email)}"
        try:
            self._client.delete(redis_key)
        except redis.RedisError:
            logger.warning("auth_rate_limit_unavailable", extra={"endpoint": "login_backoff"})

    @staticmethod
    def email_key(email: str) -> str:
        normalized = email.strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
