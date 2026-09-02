"""Client-side throttle for API-Football minute quotas (Pro = 300 req/min)."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from observability.logging import get_logger
from sports_data.provider.constants import PROVIDER_NAME

logger = get_logger(__name__)

PROVIDER_THROTTLE_WAITS_TOTAL = "provider_throttle_waits_total"
PROVIDER_THROTTLE_WAIT_SECONDS = "provider_throttle_wait_seconds"

# Safety: leave a small headroom under the plan ceiling to avoid firewall spikes.
DEFAULT_REQUESTS_PER_MINUTE = 300
DEFAULT_WINDOW_SECONDS = 60.0
DEFAULT_RATE_LIMIT_PAUSE_SECONDS = 60.0


class MinuteRateLimiter:
    """Sliding-window limiter: at most ``max_per_minute`` calls per window.

    When the window is full, sleeps until the oldest call ages out, then continues.
    """

    def __init__(
        self,
        *,
        max_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_per_minute < 1:
            raise ValueError("max_per_minute must be >= 1")
        self._max = max_per_minute
        self._window = max(1.0, float(window_seconds))
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._timestamps: deque[float] = deque()

    @property
    def max_per_minute(self) -> int:
        return self._max

    def acquire(self) -> float:
        """Block until a request slot is available. Returns seconds slept (0 if none)."""
        waited = 0.0
        while True:
            now = self._monotonic()
            while self._timestamps and (now - self._timestamps[0]) >= self._window:
                self._timestamps.popleft()
            if len(self._timestamps) < self._max:
                self._timestamps.append(now)
                return waited
            wait = self._window - (now - self._timestamps[0]) + 0.05
            wait = max(wait, 0.05)
            logger.info(
                "provider_throttle_wait",
                extra={
                    "provider": PROVIDER_NAME,
                    "wait_seconds": round(wait, 3),
                    "window_seconds": self._window,
                    "max_per_minute": self._max,
                    "requests_in_window": len(self._timestamps),
                },
            )
            self._sleep(wait)
            waited += wait
