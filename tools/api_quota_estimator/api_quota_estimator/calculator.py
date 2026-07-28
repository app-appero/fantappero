"""Deterministic quota calculator for API-Football polling plans."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .config import EndpointSpec, EstimatorConfig, ScenarioSpec, WindowSpec


@dataclass(frozen=True)
class LineItem:
    bucket: str
    endpoint: str
    scope: str
    criticality: str
    requests: float
    detail: str = ""


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    daily_requests: float
    monthly_requests: float
    peak_rpm: float
    by_bucket: dict[str, float]
    line_items: tuple[LineItem, ...]
    matches: dict[str, int]
    fantasy_users: int
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlanRecommendation:
    minimum_daily_quota: int
    sizing_basis_daily: float
    operational_margin: float
    recommended_plan: str
    recommended_daily_limit: int
    recommended_rpm_limit: int
    peak_rpm: float
    rpm_budget: float
    rpm_ok: bool
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class SimulationReport:
    version: str
    scenarios: dict[str, ScenarioResult]
    recommendation: PlanRecommendation
    quota_exhaustion_policy: dict[str, Any]
    resilience: dict[str, Any]
    assumptions_fingerprint: str


class QuotaCalculator:
    """Compute daily/monthly request volume from configurable windows."""

    WINDOW_MATCH_ATTR = {
        "pre_match": "matches_pre",
        "live": "matches_live",
        "post_match": "matches_post",
        "late_corrections": "matches_late",
    }

    def __init__(self, config: EstimatorConfig) -> None:
        self.config = config

    def simulate(self) -> SimulationReport:
        results: dict[str, ScenarioResult] = {}
        for name in ("empty", "average", "peak"):
            if name in self.config.scenarios:
                results[name] = self.estimate_scenario(name)

        # Degraded is peak load with degraded multipliers (quota near exhaustion).
        if "peak" in self.config.scenarios:
            results["degraded"] = self.estimate_scenario("peak", degraded=True, label="degraded")

        recommendation = self.recommend_plan(results)
        return SimulationReport(
            version=self.config.version,
            scenarios=results,
            recommendation=recommendation,
            quota_exhaustion_policy=self.config.raw["resilience"]["quota_exhaustion_policy"],
            resilience={
                "cache_ttl_seconds": self.config.raw["resilience"]["cache_ttl_seconds"],
                "batching": self.config.raw["resilience"]["batching"],
                "jitter": self.config.raw["resilience"]["jitter"],
                "retry": self.config.raw["resilience"]["retry"],
                "rate_limit_budget": self.config.raw["resilience"]["rate_limit_budget"],
                "circuit_breaker": self.config.raw["resilience"]["circuit_breaker"],
            },
            assumptions_fingerprint=_fingerprint(self.config.raw),
        )

    def estimate_scenario(
        self,
        scenario_name: str,
        *,
        degraded: bool = False,
        label: str | None = None,
        fantasy_users_override: int | None = None,
    ) -> ScenarioResult:
        scenario = self.config.scenarios[scenario_name]
        users = (
            self.config.fantasy_users
            if fantasy_users_override is None
            else fantasy_users_override
        )
        # Explicit: users never enter the request formula.
        _ = users

        items: list[LineItem] = []
        items.extend(self._catalog_items(degraded=degraded))

        for window_name, window in self.config.windows.items():
            match_attr = self.WINDOW_MATCH_ATTR[window_name]
            match_count = int(getattr(scenario, match_attr))
            if match_count <= 0:
                # No fixtures in this window → no polling (incl. global live batch).
                continue
            items.extend(
                self._window_items(
                    window,
                    scenario,
                    match_count=match_count,
                    degraded=degraded,
                )
            )

        by_bucket: dict[str, float] = {}
        for item in items:
            by_bucket[item.bucket] = by_bucket.get(item.bucket, 0.0) + item.requests

        raw_daily = sum(item.requests for item in items)
        daily = raw_daily * self.config.retry_amplification
        monthly = daily * self.config.calendar_days_per_month
        peak_rpm = self._peak_rpm(scenario, degraded=degraded)

        notes: list[str] = []
        if degraded:
            notes.append(
                "Degraded mode: longer intervals, fewer fixed polls, "
                f"catalog×{self.config.degraded_catalog_factor}, "
                f"drop criticalities={sorted(self.config.drop_criticalities)}"
            )
        notes.append(
            "Sports API consumption is central (SPD); fantasy_users is ignored."
        )

        return ScenarioResult(
            name=label or scenario_name,
            daily_requests=daily,
            monthly_requests=monthly,
            peak_rpm=peak_rpm,
            by_bucket={
                k: v * self.config.retry_amplification for k, v in by_bucket.items()
            },
            line_items=tuple(items),
            matches={
                "pre": scenario.matches_pre,
                "live": scenario.matches_live,
                "post": scenario.matches_post,
                "late": scenario.matches_late,
                "leagues_active": scenario.leagues_active,
                "max_concurrent_live": scenario.max_concurrent_live,
            },
            fantasy_users=users,
            notes=tuple(notes),
        )

    def monthly_blended(self, scenario_results: dict[str, ScenarioResult]) -> float:
        """Weighted monthly total from calendar month_mix (empty/average/peak)."""
        total = 0.0
        for name, days in self.config.month_mix.items():
            if name not in scenario_results:
                continue
            total += scenario_results[name].daily_requests * days
        return total

    def recommend_plan(self, results: dict[str, ScenarioResult]) -> PlanRecommendation:
        basis_name = self.config.sizing_scenario
        if basis_name not in results:
            raise KeyError(f"sizing scenario '{basis_name}' missing from results")
        basis = results[basis_name].daily_requests
        margin = self.config.operational_margin
        minimum = int(math.ceil(basis * (1.0 + margin)))
        peak_rpm = results[basis_name].peak_rpm
        rpm_budget_needed = peak_rpm / self.config.target_rpm_utilization

        chosen = None
        alternatives: list[str] = []
        for plan in self.config.plans:
            rpm_ok = plan.requests_per_minute >= rpm_budget_needed
            covers = plan.daily_requests >= minimum
            if covers and rpm_ok and chosen is None:
                chosen = plan
            elif covers:
                alternatives.append(plan.name)

        if chosen is None:
            # Fall back to highest plan even if insufficient — surface the gap.
            chosen = self.config.plans[-1]
            alternatives = []

        rpm_ok = chosen.requests_per_minute >= rpm_budget_needed
        return PlanRecommendation(
            minimum_daily_quota=minimum,
            sizing_basis_daily=basis,
            operational_margin=margin,
            recommended_plan=chosen.name,
            recommended_daily_limit=chosen.daily_requests,
            recommended_rpm_limit=chosen.requests_per_minute,
            peak_rpm=peak_rpm,
            rpm_budget=rpm_budget_needed,
            rpm_ok=rpm_ok,
            alternatives=tuple(alternatives),
        )

    def _catalog_items(self, *, degraded: bool) -> list[LineItem]:
        """Catalog sync always covers all MVP leagues (independent of matchday)."""
        items: list[LineItem] = []
        factor = self.config.degraded_catalog_factor if degraded else 1.0
        leagues = self.config.leagues_count

        for ep in self.config.catalog_endpoints:
            if degraded and ep.criticality in self.config.drop_criticalities:
                continue
            units = self._scope_units(ep.scope, match_count=0, leagues_active=leagues)
            req = ep.calls * units * factor
            items.append(
                LineItem(
                    bucket="catalog",
                    endpoint=ep.endpoint,
                    scope=ep.scope,
                    criticality=ep.criticality,
                    requests=req,
                    detail=f"calls={ep.calls} units={units} factor={factor}",
                )
            )
        return items

    def _window_items(
        self,
        window: WindowSpec,
        scenario: ScenarioSpec,
        *,
        match_count: int,
        degraded: bool,
    ) -> list[LineItem]:
        items: list[LineItem] = []
        leagues = scenario.leagues_active
        for ep in window.endpoints:
            if degraded and ep.criticality in self.config.drop_criticalities:
                continue
            req = self._endpoint_requests(
                ep,
                window,
                match_count=match_count,
                leagues_active=leagues,
                degraded=degraded,
            )
            items.append(
                LineItem(
                    bucket=window.name,
                    endpoint=ep.endpoint,
                    scope=ep.scope,
                    criticality=ep.criticality,
                    requests=req,
                    detail=self._endpoint_detail(ep, window, degraded=degraded),
                )
            )
        return items

    def _endpoint_requests(
        self,
        ep: EndpointSpec,
        window: WindowSpec,
        *,
        match_count: int,
        leagues_active: int,
        degraded: bool,
    ) -> float:
        units = self._scope_units(
            ep.scope, match_count=match_count, leagues_active=leagues_active
        )
        if units == 0:
            return 0.0

        if ep.fixed_polls is not None:
            polls = float(ep.fixed_polls)
            if degraded:
                polls *= self.config.degraded_fixed_polls_factor
            return polls * units * ep.calls

        if ep.interval_seconds is None or ep.interval_seconds <= 0:
            raise ValueError(
                f"{window.name}/{ep.endpoint}: need interval_seconds or fixed_polls"
            )

        interval = float(ep.interval_seconds)
        if degraded:
            interval *= self.config.degraded_interval_factor

        duration_seconds = window.duration_minutes * 60.0
        cycles = duration_seconds / interval
        return cycles * units * ep.calls

    def _endpoint_detail(
        self, ep: EndpointSpec, window: WindowSpec, *, degraded: bool
    ) -> str:
        if ep.fixed_polls is not None:
            polls = ep.fixed_polls
            if degraded:
                polls = polls * self.config.degraded_fixed_polls_factor
            return f"fixed_polls={polls}"
        interval = ep.interval_seconds or 0.0
        if degraded:
            interval *= self.config.degraded_interval_factor
        return f"duration_min={window.duration_minutes} interval_s={interval}"

    @staticmethod
    def _scope_units(scope: str, *, match_count: int, leagues_active: int) -> int:
        if scope == "global":
            return 1
        if scope == "per_league":
            return max(0, leagues_active)
        if scope == "per_match":
            return max(0, match_count)
        raise ValueError(f"unknown scope: {scope}")

    def _peak_rpm(self, scenario: ScenarioSpec, *, degraded: bool) -> float:
        """Worst-minute request rate during live window."""
        if scenario.matches_live <= 0 or scenario.max_concurrent_live <= 0:
            return 0.0
        live = self.config.windows["live"]
        concurrent = scenario.max_concurrent_live
        rpm = 0.0
        for ep in live.endpoints:
            if degraded and ep.criticality in self.config.drop_criticalities:
                continue
            if ep.interval_seconds is None:
                continue
            interval = float(ep.interval_seconds)
            if degraded:
                interval *= self.config.degraded_interval_factor
            if interval <= 0:
                continue
            cycles_per_minute = 60.0 / interval
            if ep.scope == "global":
                units = 1
            elif ep.scope == "per_league":
                units = scenario.leagues_active
            else:
                units = concurrent
            rpm += cycles_per_minute * units * ep.calls
        return rpm * self.config.retry_amplification

def _fingerprint(raw: dict[str, Any]) -> str:
    """Stable short fingerprint of assumptions (not cryptographic)."""
    import hashlib
    import json

    payload = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
