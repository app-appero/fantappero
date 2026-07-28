"""Load and validate estimator configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "default.json"


@dataclass(frozen=True)
class EndpointSpec:
    endpoint: str
    scope: str  # global | per_league | per_match
    criticality: str = "medium"
    interval_seconds: float | None = None
    fixed_polls: int | None = None
    calls: int = 1
    note: str = ""


@dataclass(frozen=True)
class WindowSpec:
    name: str
    duration_minutes: float
    endpoints: tuple[EndpointSpec, ...]
    description: str = ""


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    matches_pre: int
    matches_live: int
    matches_post: int
    matches_late: int
    leagues_active: int
    max_concurrent_live: int
    description: str = ""


@dataclass(frozen=True)
class PlanSpec:
    name: str
    daily_requests: int
    requests_per_minute: int


@dataclass(frozen=True)
class EstimatorConfig:
    raw: dict[str, Any]
    leagues_count: int
    fantasy_users: int
    windows: dict[str, WindowSpec]
    catalog_endpoints: tuple[EndpointSpec, ...]
    scenarios: dict[str, ScenarioSpec]
    plans: tuple[PlanSpec, ...]
    calendar_days_per_month: int
    month_mix: dict[str, int]
    retry_amplification: float
    degraded_interval_factor: float
    degraded_fixed_polls_factor: float
    degraded_catalog_factor: float
    drop_criticalities: frozenset[str]
    operational_margin: float
    sizing_scenario: str
    target_rpm_utilization: float
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def version(self) -> str:
        return str(self.meta.get("version", "0"))


def _endpoint(data: dict[str, Any]) -> EndpointSpec:
    return EndpointSpec(
        endpoint=str(data["endpoint"]),
        scope=str(data["scope"]),
        criticality=str(data.get("criticality", "medium")),
        interval_seconds=(
            float(data["interval_seconds"]) if "interval_seconds" in data else None
        ),
        fixed_polls=int(data["fixed_polls"]) if "fixed_polls" in data else None,
        calls=int(data.get("calls", 1)),
        note=str(data.get("note", "")),
    )


def _window(name: str, data: dict[str, Any]) -> WindowSpec:
    return WindowSpec(
        name=name,
        duration_minutes=float(data["duration_minutes"]),
        endpoints=tuple(_endpoint(e) for e in data.get("endpoints", [])),
        description=str(data.get("description", "")),
    )


def load_config(path: Path | None = None) -> EstimatorConfig:
    config_path = path or DEFAULT_CONFIG_PATH
    raw = json.loads(config_path.read_text(encoding="utf-8-sig"))
    return parse_config(raw)


def parse_config(raw: dict[str, Any]) -> EstimatorConfig:
    windows_raw = raw["windows"]
    windows = {
        "pre_match": _window("pre_match", windows_raw["pre_match"]),
        "live": _window("live", windows_raw["live"]),
        "post_match": _window("post_match", windows_raw["post_match"]),
        "late_corrections": _window(
            "late_corrections", windows_raw["late_corrections"]
        ),
    }

    scenarios: dict[str, ScenarioSpec] = {}
    for name, s in raw["scenarios"].items():
        scenarios[name] = ScenarioSpec(
            name=name,
            matches_pre=int(s["matches_pre"]),
            matches_live=int(s["matches_live"]),
            matches_post=int(s["matches_post"]),
            matches_late=int(s["matches_late"]),
            leagues_active=int(s["leagues_active"]),
            max_concurrent_live=int(s["max_concurrent_live"]),
            description=str(s.get("description", "")),
        )

    plans = tuple(
        PlanSpec(
            name=str(p["name"]),
            daily_requests=int(p["daily_requests"]),
            requests_per_minute=int(p["requests_per_minute"]),
        )
        for p in raw["plans"]
    )

    degraded = raw["degraded_multipliers"]
    resilience = raw["resilience"]
    recommendation = raw["recommendation"]
    calendar = raw["calendar"]

    return EstimatorConfig(
        raw=raw,
        leagues_count=int(raw["leagues"]["count"]),
        fantasy_users=int(raw.get("fantasy_users", 0)),
        windows=windows,
        catalog_endpoints=tuple(
            _endpoint(e) for e in raw["catalog_daily"]["endpoints"]
        ),
        scenarios=scenarios,
        plans=plans,
        calendar_days_per_month=int(calendar["days_per_month"]),
        month_mix={k: int(v) for k, v in calendar["month_mix"].items()},
        retry_amplification=float(resilience["retry"]["expected_amplification"]),
        degraded_interval_factor=float(degraded["interval_factor"]),
        degraded_fixed_polls_factor=float(degraded["fixed_polls_factor"]),
        degraded_catalog_factor=float(degraded["catalog_factor"]),
        drop_criticalities=frozenset(degraded.get("drop_criticalities", [])),
        operational_margin=float(recommendation["operational_margin"]),
        sizing_scenario=str(recommendation["sizing_scenario"]),
        target_rpm_utilization=float(
            resilience["rate_limit_budget"]["target_utilization_of_plan_rpm"]
        ),
        meta=dict(raw.get("meta", {})),
    )


def with_overrides(config: EstimatorConfig, overrides: dict[str, Any]) -> EstimatorConfig:
    """Deep-merge overrides into a copy of config.raw and re-parse."""
    merged = _deep_merge(config.raw, overrides)
    return parse_config(merged)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out
