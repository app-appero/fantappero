"""Rate limiter unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

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
