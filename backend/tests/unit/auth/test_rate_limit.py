"""Rate limiter unit tests."""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock

import pytest
import redis

from auth.exceptions import RateLimitExceededError
from auth.rate_limit import AuthRateLimiter


def test_rate_limit_allows_under_threshold() -> None:
    client = MagicMock()
    client.incr.return_value = 1
    limiter = AuthRateLimiter.__new__(AuthRateLimiter)
    limiter._client = client
    limiter.check(endpoint="login", key="127.0.0.1", limit=5, window_seconds=60)
    client.expire.assert_called_once()


def test_rate_limit_blocks_over_threshold() -> None:
    client = MagicMock()
    client.incr.return_value = 6
    limiter = AuthRateLimiter.__new__(AuthRateLimiter)
    limiter._client = client
    with pytest.raises(RateLimitExceededError):
        limiter.check(endpoint="login", key="127.0.0.1", limit=5, window_seconds=60)


@pytest.fixture
def live_limiter() -> AuthRateLimiter:
    """A real Redis-backed limiter: the backoff logic leans on HINCRBY/HSET/EXPIRE
    semantics a mock would only approximate."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        pytest.skip("REDIS_URL not set — skipping live-Redis rate limit tests")
    limiter = AuthRateLimiter(url)
    try:
        limiter._client.ping()
    except redis.RedisError:
        pytest.skip("Redis unreachable — skipping live-Redis rate limit tests")
    yield limiter
    for key in limiter._client.scan_iter("auth:login_backoff:*"):
        limiter._client.delete(key)


def test_login_backoff_leaves_the_first_five_failures_free(
    live_limiter: AuthRateLimiter,
) -> None:
    email = f"backoff-{uuid.uuid4()}@example.com"
    for _ in range(5):
        live_limiter.check_login_backoff(email)  # must never raise yet
        live_limiter.record_login_failure(email)


def test_login_backoff_blocks_the_sixth_failure_then_lifts_after_the_wait(
    monkeypatch: pytest.MonkeyPatch, live_limiter: AuthRateLimiter
) -> None:
    email = f"backoff-{uuid.uuid4()}@example.com"
    now = 1_700_000_000.0
    monkeypatch.setattr("auth.rate_limit.time.time", lambda: now)
    for _ in range(6):
        live_limiter.record_login_failure(email)

    with pytest.raises(RateLimitExceededError):
        live_limiter.check_login_backoff(email)

    # Still inside the 30s wait earned by the 6th failure.
    monkeypatch.setattr("auth.rate_limit.time.time", lambda: now + 29)
    with pytest.raises(RateLimitExceededError):
        live_limiter.check_login_backoff(email)

    # Past it: the next attempt is allowed through (does not reset the counter on its own).
    monkeypatch.setattr("auth.rate_limit.time.time", lambda: now + 31)
    live_limiter.check_login_backoff(email)


def test_login_backoff_grows_with_each_further_failure(
    monkeypatch: pytest.MonkeyPatch, live_limiter: AuthRateLimiter
) -> None:
    email = f"backoff-{uuid.uuid4()}@example.com"
    now = 1_700_000_000.0
    monkeypatch.setattr("auth.rate_limit.time.time", lambda: now)
    for _ in range(8):  # two failures past the 6th: schedule index 2 → 600s wait
        live_limiter.record_login_failure(email)

    monkeypatch.setattr("auth.rate_limit.time.time", lambda: now + 120)
    with pytest.raises(RateLimitExceededError):
        live_limiter.check_login_backoff(email)

    monkeypatch.setattr("auth.rate_limit.time.time", lambda: now + 601)
    live_limiter.check_login_backoff(email)


def test_login_success_clears_the_backoff(live_limiter: AuthRateLimiter) -> None:
    email = f"backoff-{uuid.uuid4()}@example.com"
    for _ in range(10):
        live_limiter.record_login_failure(email)
    live_limiter.record_login_success(email)
    live_limiter.check_login_backoff(email)  # no wait left: must not raise
