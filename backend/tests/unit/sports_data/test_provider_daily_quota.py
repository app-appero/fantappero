"""Quota giornaliera del fornitore: sonda ``/status`` e quota del giorno finita (24/11).

Sul pilota la sonda ``/status`` falliva a ogni giro dopo ``GET /status 200``: la risposta ha
``response`` come oggetto e il parser voleva una lista, quindi la modalità quota restava sempre
``ok``. Il 23/11 la quota del giorno è finita e il fornitore ha rifiutato tutto per due ore con
``errors.requests`` («request limit for the day»), letto come un errore generico.

Le risposte seguono la forma documentata di API-Football v3; nessuna chiamata reale.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import pytest

from observability.metrics import reset_metrics
from sports_data.provider.client import ApiFootballClient
from sports_data.provider.envelope import (
    STATUS_ENDPOINT,
    daily_quota_from_status,
    errors_indicate_daily_limit,
    errors_indicate_rate_limit,
    parse_envelope,
)
from sports_data.provider.errors import (
    ProviderDailyLimitError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from sports_data.provider.types import ProviderRateLimit
from sports_data.scheduler.quota import QuotaMode, resolve_quota_mode

DAILY_LIMIT_ERRORS = {
    "requests": (
        "You have reached the request limit for the day, Go to "
        "https://dashboard.api-football.com to upgrade your plan."
    )
}


def status_payload(*, current: int, limit_day: int) -> dict[str, Any]:
    """``GET /status`` di API-Football v3: ``response`` è un oggetto, ``parameters`` una lista."""
    return {
        "get": "status",
        "parameters": [],
        "errors": [],
        "results": 1,
        "paging": {"current": 1, "total": 1},
        "response": {
            "account": {"firstname": "Test", "lastname": "Test", "email": "test@example.com"},
            "subscription": {"plan": "Pro", "end": "2027-06-30T00:00:00+00:00", "active": True},
            "requests": {"current": current, "limit_day": limit_day},
        },
    }


def daily_limit_payload(endpoint: str = "fixtures") -> dict[str, Any]:
    return {
        "get": endpoint,
        "parameters": {"live": "all"},
        "errors": DAILY_LIMIT_ERRORS,
        "results": 0,
        "paging": {"current": 1, "total": 1},
        "response": [],
    }


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    reset_metrics()
    yield
    reset_metrics()


def _client(handler: Any, **kwargs: Any) -> ApiFootballClient:
    return ApiFootballClient(
        api_key="test-key-not-a-secret",
        base_url="https://provider.test",
        transport=httpx.MockTransport(handler),
        max_retries=0,
        retry_backoff_seconds=0,
        requests_per_minute=1000,
        **kwargs,
    )


def test_status_response_object_is_parsed() -> None:
    envelope = parse_envelope(status_payload(current=1200, limit_day=7500), endpoint="/status")
    assert envelope.endpoint == STATUS_ENDPOINT
    assert envelope.results == 1
    assert len(envelope.response) == 1
    assert envelope.response[0]["requests"] == {"current": 1200, "limit_day": 7500}
    assert daily_quota_from_status(envelope) == ProviderRateLimit(limit=7500, remaining=6300)


def test_a_response_object_is_still_rejected_on_list_endpoints() -> None:
    payload = status_payload(current=1, limit_day=10)
    payload["get"] = "fixtures"
    with pytest.raises(ProviderResponseError):
        parse_envelope(payload, endpoint="/fixtures")


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (1000, QuotaMode.OK),  # 86,7% rimasto
        (5800, QuotaMode.WARN),  # 22,7% ≤ 25%
        (6500, QuotaMode.DEGRADE),  # 13,3% ≤ 15%
        (7200, QuotaMode.CRITICAL_ONLY),  # 4% ≤ 5%
        (7600, QuotaMode.CRITICAL_ONLY),  # oltre il limite: rimasto 0
    ],
)
def test_quota_mode_from_the_status_body(current: int, expected: QuotaMode) -> None:
    envelope = parse_envelope(status_payload(current=current, limit_day=7500), endpoint="/status")
    assert resolve_quota_mode(daily_quota_from_status(envelope)) == expected


def test_status_without_requests_falls_back_to_the_headers() -> None:
    payload = status_payload(current=0, limit_day=0)
    payload["response"] = {"account": {}}
    headers = ProviderRateLimit(limit=100, remaining=10)
    envelope = parse_envelope(payload, endpoint="/status", rate_limit=headers)
    assert daily_quota_from_status(envelope) == headers


def test_client_probe_of_status_works_end_to_end() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/status"
        return httpx.Response(200, json=status_payload(current=7000, limit_day=7500))

    with _client(handler) as client:
        quota = daily_quota_from_status(client.get(STATUS_ENDPOINT, fetch_all_pages=False))
    assert quota == ProviderRateLimit(limit=7500, remaining=500)
    assert resolve_quota_mode(quota) == QuotaMode.DEGRADE  # 6,7%


def test_daily_limit_errors_are_recognised_and_distinct_from_the_minute_limit() -> None:
    assert errors_indicate_daily_limit(DAILY_LIMIT_ERRORS)
    assert not errors_indicate_rate_limit(DAILY_LIMIT_ERRORS)
    minute_limit = {"rateLimit": "Too many requests. Your rate limit is 10 requests per minute."}
    assert errors_indicate_rate_limit(minute_limit)
    assert not errors_indicate_daily_limit(minute_limit)
    assert not errors_indicate_daily_limit({"token": "Error/Missing application key."})
    assert not errors_indicate_daily_limit([])


def test_parse_envelope_raises_the_daily_limit_error() -> None:
    with pytest.raises(ProviderDailyLimitError) as exc:
        parse_envelope(daily_limit_payload(), endpoint="/fixtures")
    assert isinstance(exc.value, ProviderRateLimitError)  # chi gestisce già il limite lo vede
    assert exc.value.code == "provider_daily_limit_reached"
    assert exc.value.remaining == 0


def test_client_does_not_pause_on_the_daily_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Il limite al minuto si aspetta un minuto; quello del giorno no: niente pause."""
    attempts = {"n": 0}
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: slept.append(seconds))

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(200, json=daily_limit_payload())

    with _client(handler, rate_limit_pause_seconds=60) as client:
        with pytest.raises(ProviderDailyLimitError):
            client.get("/fixtures", {"live": "all"})
    assert attempts["n"] == 1
    assert slept == []


def test_client_logs_the_daily_limit_code_in_the_message(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=daily_limit_payload("players"))

    with caplog.at_level("WARNING", logger="sports_data.provider.client"):
        with _client(handler) as client:
            with pytest.raises(ProviderDailyLimitError):
                client.get("/players", {"id": 1, "season": 2025})
    messages = [record.getMessage() for record in caplog.records]
    assert "provider_daily_limit_reached endpoint=/players code=provider_daily_limit_reached" in (
        messages
    )
