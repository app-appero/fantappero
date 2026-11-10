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


def test_login_backoff_leaves_the_first_five_attempts_free(
    live_limiter: AuthRateLimiter,
) -> None:
    email = f"backoff-{uuid.uuid4()}@example.com"
    for _ in range(5):
        live_limiter.check_login_backoff(email)  # must never raise, and reserves the attempt


def test_login_backoff_blocks_the_sixth_attempt_then_lifts_after_the_wait(
    monkeypatch: pytest.MonkeyPatch, live_limiter: AuthRateLimiter
) -> None:
    email = f"backoff-{uuid.uuid4()}@example.com"
    now = 1_700_000_000.0
    monkeypatch.setattr("auth.rate_limit.time.time", lambda: now)
    for _ in range(5):
        live_limiter.check_login_backoff(email)

    # The 6th attempt needs the 30s wait earned by using up the 5 free ones.
    with pytest.raises(RateLimitExceededError):
        live_limiter.check_login_backoff(email)

    # Still inside that wait — and a blocked attempt leaves the counter untouched,
    # so retrying here doesn't push it into a longer tier.
    monkeypatch.setattr("auth.rate_limit.time.time", lambda: now + 29)
    with pytest.raises(RateLimitExceededError):
        live_limiter.check_login_backoff(email)

    # Past it: the next attempt is allowed through, and now counts as the 6th reservation.
    monkeypatch.setattr("auth.rate_limit.time.time", lambda: now + 31)
    live_limiter.check_login_backoff(email)


def test_login_backoff_grows_with_each_further_attempt(
    monkeypatch: pytest.MonkeyPatch, live_limiter: AuthRateLimiter
) -> None:
    email = f"backoff-{uuid.uuid4()}@example.com"
    now = 1_700_000_000.0
    # Reserve 8 attempts, each spaced out past whatever wait its own tier demands —
    # two attempts past the free ones lands on the capped (longest) 600s tier.
    for i in range(8):
        monkeypatch.setattr("auth.rate_limit.time.time", lambda now=now: now)
        live_limiter.check_login_backoff(email)
        if i < 7:
            now += 700

    # Right after the 8th reservation: well inside the 600s wait it now demands.
    monkeypatch.setattr("auth.rate_limit.time.time", lambda now=now: now)
    with pytest.raises(RateLimitExceededError):
        live_limiter.check_login_backoff(email)

    monkeypatch.setattr("auth.rate_limit.time.time", lambda now=now: now + 599)
    with pytest.raises(RateLimitExceededError):
        live_limiter.check_login_backoff(email)

    monkeypatch.setattr("auth.rate_limit.time.time", lambda now=now: now + 601)
    live_limiter.check_login_backoff(email)


def test_login_success_clears_the_backoff(
    monkeypatch: pytest.MonkeyPatch, live_limiter: AuthRateLimiter
) -> None:
    email = f"backoff-{uuid.uuid4()}@example.com"
    now = 1_700_000_000.0
    for _ in range(10):
        monkeypatch.setattr("auth.rate_limit.time.time", lambda now=now: now)
        live_limiter.check_login_backoff(email)
        now += 700
    live_limiter.record_login_success(email)
    monkeypatch.setattr("auth.rate_limit.time.time", lambda now=now: now)
    live_limiter.check_login_backoff(email)  # no wait left: must not raise


def test_login_backoff_does_not_double_count_concurrent_attempts(
    live_limiter: AuthRateLimiter,
) -> None:
    """The race this fixes: a burst of concurrent requests for the same account must be
    serialized by Redis, not all read the same stale counter and sail through together."""
    import threading

    email = f"backoff-{uuid.uuid4()}@example.com"
    allowed = 0
    blocked = 0
    lock = threading.Lock()

    def attempt() -> None:
        nonlocal allowed, blocked
        try:
            live_limiter.check_login_backoff(email)
        except RateLimitExceededError:
            with lock:
                blocked += 1
        else:
            with lock:
                allowed += 1

    threads = [threading.Thread(target=attempt) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Exactly the free attempts get through at once; every other concurrent attempt in
    # the same instant is blocked — never more allowed than the account actually earned.
    assert allowed == 5
    assert blocked == 15
