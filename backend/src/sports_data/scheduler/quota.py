"""Quota degradation modes for sports polling (EP04-06 / EP00-04)."""

from __future__ import annotations

from enum import StrEnum

from sports_data.provider.types import ProviderRateLimit

# Fractions of daily remaining / limit — api_football_polling_plan.md §5
WARN_REMAINING_FRACTION = 0.25
DEGRADE_REMAINING_FRACTION = 0.15
CRITICAL_ONLY_REMAINING_FRACTION = 0.05

# Degraded multipliers (tools/api_quota_estimator/config/default.json)
DEGRADED_INTERVAL_FACTOR = 2.5
DEGRADED_FIXED_POLLS_FACTOR = 0.5
DROP_CRITICALITIES_IN_DEGRADE = frozenset({"low"})


class QuotaMode(StrEnum):
    OK = "ok"
    WARN = "warn"
    DEGRADE = "degrade"
    CRITICAL_ONLY = "critical_only"


def remaining_fraction(rate_limit: ProviderRateLimit | None) -> float | None:
    if rate_limit is None:
        return None
    if rate_limit.remaining is None or rate_limit.limit is None:
        return None
    if rate_limit.limit <= 0:
        return None
    return max(0.0, float(rate_limit.remaining) / float(rate_limit.limit))


def resolve_quota_mode(
    rate_limit: ProviderRateLimit | None,
    *,
    remaining: int | None = None,
    limit: int | None = None,
) -> QuotaMode:
    """Map provider daily remaining headers to an operational mode."""
    rem = remaining if remaining is not None else (rate_limit.remaining if rate_limit else None)
    lim = limit if limit is not None else (rate_limit.limit if rate_limit else None)
    if rem is None or lim is None or lim <= 0:
        return QuotaMode.OK
    fraction = max(0.0, float(rem) / float(lim))
    if fraction <= CRITICAL_ONLY_REMAINING_FRACTION:
        return QuotaMode.CRITICAL_ONLY
    if fraction <= DEGRADE_REMAINING_FRACTION:
        return QuotaMode.DEGRADE
    if fraction <= WARN_REMAINING_FRACTION:
        return QuotaMode.WARN
    return QuotaMode.OK


def interval_seconds(base_seconds: float, mode: QuotaMode) -> float:
    """Stretch polling intervals when quota is degraded / critical."""
    if mode in (QuotaMode.DEGRADE, QuotaMode.CRITICAL_ONLY):
        return base_seconds * DEGRADED_INTERVAL_FACTOR
    return base_seconds


def allow_criticality(criticality: str, mode: QuotaMode) -> bool:
    """Return False when the endpoint criticality must be dropped for the mode."""
    level = (criticality or "").strip().lower()
    if mode == QuotaMode.CRITICAL_ONLY:
        return level in {"critical", "high"}
    if mode == QuotaMode.DEGRADE:
        return level not in DROP_CRITICALITIES_IN_DEGRADE
    return True


def max_fixtures_for_mode(base_limit: int | None, mode: QuotaMode) -> int | None:
    """Reduce per-run fixture fan-out under degrade / critical_only."""
    if base_limit is None:
        if mode == QuotaMode.CRITICAL_ONLY:
            return 20
        if mode == QuotaMode.DEGRADE:
            return 40
        return None
    if mode in (QuotaMode.DEGRADE, QuotaMode.CRITICAL_ONLY):
        reduced = max(1, int(base_limit * DEGRADED_FIXED_POLLS_FACTOR))
        return reduced
    return base_limit
