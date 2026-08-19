"""Unit tests for EP00-04 API quota calculator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api_quota_estimator.calculator import QuotaCalculator
from api_quota_estimator.config import load_config, with_overrides

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "default.json"


@pytest.fixture
def config():
    return load_config(DEFAULT_CONFIG)


@pytest.fixture
def calc(config):
    return QuotaCalculator(config)


def test_empty_day_is_catalog_only(calc):
    result = calc.estimate_scenario("empty")
    assert result.matches["live"] == 0
    assert result.by_bucket.get("live", 0.0) == 0.0
    assert result.by_bucket.get("pre_match", 0.0) == 0.0
    assert result.by_bucket.get("post_match", 0.0) == 0.0
    assert result.by_bucket.get("late_corrections", 0.0) == 0.0
    assert result.by_bucket["catalog"] > 0
    assert result.daily_requests == pytest.approx(
        result.by_bucket["catalog"], rel=1e-9
    )


def test_normal_matchday_exceeds_empty(calc):
    empty = calc.estimate_scenario("empty")
    average = calc.estimate_scenario("average")
    assert average.daily_requests > empty.daily_requests
    assert average.by_bucket["live"] > 0
    assert average.by_bucket["pre_match"] > 0
    assert average.by_bucket["post_match"] > 0


def test_peak_exceeds_average(calc):
    average = calc.estimate_scenario("average")
    peak = calc.estimate_scenario("peak")
    assert peak.daily_requests > average.daily_requests
    assert peak.matches["live"] > average.matches["live"]
    assert peak.peak_rpm > average.peak_rpm


def test_fantasy_users_do_not_affect_sports_consumption(config):
    low = QuotaCalculator(
        with_overrides(config, {"fantasy_users": 1})
    ).estimate_scenario("peak")
    high = QuotaCalculator(
        with_overrides(config, {"fantasy_users": 1_000_000})
    ).estimate_scenario("peak")
    assert low.daily_requests == high.daily_requests
    assert low.monthly_requests == high.monthly_requests
    assert low.peak_rpm == high.peak_rpm
    assert low.by_bucket == high.by_bucket


def test_simulate_includes_medium_peak_degraded(calc):
    report = calc.simulate()
    assert set(report.scenarios) >= {"average", "peak", "degraded", "empty"}
    assert report.scenarios["degraded"].daily_requests < report.scenarios["peak"].daily_requests
    assert report.scenarios["degraded"].peak_rpm < report.scenarios["peak"].peak_rpm
    assert report.recommendation.minimum_daily_quota > 0
    assert report.recommendation.recommended_plan in {"Free", "Pro", "Ultra", "Mega"}


def test_monthly_is_daily_times_calendar_days(calc, config):
    result = calc.estimate_scenario("average")
    assert result.monthly_requests == pytest.approx(
        result.daily_requests * config.calendar_days_per_month
    )


def test_match_count_override_is_repeatable(config):
    a = QuotaCalculator(
        with_overrides(
            config,
            {"scenarios": {"average": {"matches_live": 10, "matches_pre": 10, "matches_post": 10, "matches_late": 10}}},
        )
    ).estimate_scenario("average")
    b = QuotaCalculator(
        with_overrides(
            config,
            {"scenarios": {"average": {"matches_live": 10, "matches_pre": 10, "matches_post": 10, "matches_late": 10}}},
        )
    ).estimate_scenario("average")
    assert a.daily_requests == b.daily_requests


def test_live_events_scale_linearly_with_matches(config):
    one = QuotaCalculator(
        with_overrides(
            config,
            {
                "scenarios": {
                    "average": {
                        "matches_live": 1,
                        "matches_pre": 0,
                        "matches_post": 0,
                        "matches_late": 0,
                        "leagues_active": 1,
                        "max_concurrent_live": 1,
                    }
                },
                "catalog_daily": {"endpoints": []},
                "windows": {
                    "pre_match": {"endpoints": []},
                    "post_match": {"endpoints": []},
                    "late_corrections": {"endpoints": []},
                    "live": {
                        "duration_minutes": 100,
                        "endpoints": [
                            {
                                "endpoint": "/fixtures/events",
                                "scope": "per_match",
                                "interval_seconds": 60,
                                "criticality": "critical",
                            }
                        ],
                    },
                },
                "resilience": {"retry": {"expected_amplification": 1.0}},
            },
        )
    ).estimate_scenario("average")
    ten = QuotaCalculator(
        with_overrides(
            config,
            {
                "scenarios": {
                    "average": {
                        "matches_live": 10,
                        "matches_pre": 0,
                        "matches_post": 0,
                        "matches_late": 0,
                        "leagues_active": 1,
                        "max_concurrent_live": 10,
                    }
                },
                "catalog_daily": {"endpoints": []},
                "windows": {
                    "pre_match": {"endpoints": []},
                    "post_match": {"endpoints": []},
                    "late_corrections": {"endpoints": []},
                    "live": {
                        "duration_minutes": 100,
                        "endpoints": [
                            {
                                "endpoint": "/fixtures/events",
                                "scope": "per_match",
                                "interval_seconds": 60,
                                "criticality": "critical",
                            }
                        ],
                    },
                },
                "resilience": {"retry": {"expected_amplification": 1.0}},
            },
        )
    ).estimate_scenario("average")
    assert ten.daily_requests == pytest.approx(one.daily_requests * 10)


def test_default_config_is_valid_json():
    raw = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8-sig"))
    assert raw["meta"]["card"] == "EP00-04"
    assert raw["leagues"]["count"] == 5
