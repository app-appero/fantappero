"""Quiet-hours window check for external notification channels (EP09-05)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def is_within_quiet_hours(
    *,
    now: datetime,
    timezone_name: str,
    start_hour: int | None,
    end_hour: int | None,
) -> bool:
    """True when ``now`` falls inside the user's configured quiet-hours window.

    Both bounds unset means no quiet hours are configured (never quiet). The
    window may wrap midnight (e.g. 22 -> 8). Only external channels honor
    this — the in-app center is never suppressed.
    """
    if start_hour is None or end_hour is None or start_hour == end_hour:
        return False
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = UTC
    local_hour = now.astimezone(tz).hour
    if start_hour < end_hour:
        return start_hour <= local_hour < end_hour
    return local_hour >= start_hour or local_hour < end_hour
