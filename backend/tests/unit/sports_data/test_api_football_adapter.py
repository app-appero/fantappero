"""Unit tests for API-Football adapter: envelope, mapping, client, idempotency (EP04-01)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from observability.metrics import get_metrics, reset_metrics
from sports_data.provider.client import (
    PROVIDER_REQUESTS_TOTAL,
    PROVIDER_RETRIES_TOTAL,
    ApiFootballClient,
)
from sports_data.provider.constants import PROVIDER_NAME
from sports_data.provider.envelope import merge_envelopes, parse_envelope
from sports_data.provider.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderHttpError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from sports_data.provider.hashing import payload_sha256, request_fingerprint
from sports_data.provider.mapping import map_clubs, map_competitions, map_fixtures
from sports_data.provider.types import ProviderEnvelope, ProviderPaging

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    reset_metrics()
    yield
    reset_metrics()


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def test_parse_envelope_from_leagues_fixture() -> None:
    payload = _load("reference/leagues.json")
    envelope = parse_envelope(payload, endpoint="/leagues")
    assert envelope.endpoint == "/leagues"
    assert envelope.results == 5
    assert envelope.paging.current == 1
    assert not envelope.has_errors
    mapped = map_competitions(envelope)
    assert len(mapped) == 5
    ids = {c.provider_id for c in mapped}
    assert ids == {39, 140, 135, 78, 61}
    premier = next(c for c in mapped if c.provider_id == 39)
    assert premier.name == "Premier League"
    assert premier.country == "England"
    assert premier.season_year == 2026


def test_map_clubs_from_teams_fixture() -> None:
    envelope = parse_envelope(_load("reference/teams.json"), endpoint="/teams")
    clubs = map_clubs(envelope)
    assert len(clubs) == 36
    assert any(c.provider_id == 165 and c.name == "Borussia Dortmund" for c in clubs)


def test_map_fixtures_from_corpus() -> None:
    envelope = parse_envelope(
        _load("matches/78/1388315/fixtures.json"),
        endpoint="/fixtures",
    )
    fixtures = map_fixtures(envelope)
    assert len(fixtures) == 1
    fx = fixtures[0]
    assert fx.provider_id == 1388315
    assert fx.competition_provider_id == 78
    assert fx.home_club_provider_id == 186
    assert fx.away_club_provider_id == 165
    assert fx.status_short == "FT"
    assert fx.home_goals == 3
    assert fx.away_goals == 3
    assert fx.kickoff_at is not None


def test_mapping_idempotent_on_same_payload() -> None:
    payload = _load("reference/leagues.json")
    a = map_competitions(parse_envelope(payload))
    b = map_competitions(parse_envelope(payload))
    assert [c.provider_id for c in a] == [c.provider_id for c in b]
    assert payload_sha256(payload) == payload_sha256(json.loads(json.dumps(payload)))


def test_request_fingerprint_stable_and_ignores_page() -> None:
    fp1 = request_fingerprint("/leagues", {"current": "true", "page": 1})
    fp2 = request_fingerprint("/leagues", {"page": 2, "current": "true"})
    fp3 = request_fingerprint("/leagues", {"current": "true"})
    assert fp1 == fp2 == fp3
    assert fp1 != request_fingerprint("/teams", {"current": "true"})


def test_parse_envelope_raises_on_provider_errors() -> None:
    with pytest.raises(ProviderResponseError):
        parse_envelope(
            {
                "get": "leagues",
                "parameters": {},
                "errors": {"token": "Error"},
                "results": 0,
                "paging": {"current": 1, "total": 1},
                "response": [],
            }
        )


def test_parse_envelope_raises_rate_limit_from_body_errors() -> None:
    from sports_data.provider.errors import ProviderRateLimitError

    with pytest.raises(ProviderRateLimitError) as exc:
        parse_envelope(
            {
                "get": "players/squads",
                "parameters": {"team": "83"},
                "errors": {
                    "rateLimit": (
                        "Too many requests. You have exceeded the limit of "
                        "requests per minute of your subscription."
                    )
                },
                "results": 0,
                "paging": {"current": 1, "total": 1},
                "response": [],
            },
            endpoint="/players/squads",
        )
    assert "Quota API-Football" in str(exc.value)
    assert exc.value.endpoint == "/players/squads"


def test_merge_envelopes_concatenates_pages() -> None:
    page1 = ProviderEnvelope(
        endpoint="/teams",
        parameters={"league": "39"},
        errors=[],
        results=1,
        paging=ProviderPaging(current=1, total=2),
        response=[{"team": {"id": 1, "name": "A"}}],
        raw={},
    )
    page2 = ProviderEnvelope(
        endpoint="/teams",
        parameters={"league": "39", "page": "2"},
        errors=[],
        results=1,
        paging=ProviderPaging(current=2, total=2),
        response=[{"team": {"id": 2, "name": "B"}}],
        raw={},
    )
    merged = merge_envelopes([page1, page2])
    assert merged.results == 2
    assert len(merged.response) == 2
    assert merged.paging.total == 1


def test_client_requires_api_key() -> None:
    with pytest.raises(ProviderConfigError):
        ApiFootballClient(api_key=None)
    with pytest.raises(ProviderConfigError):
        ApiFootballClient(api_key="  ")


def test_client_get_single_page_with_mock_transport() -> None:
    payload = _load("reference/leagues.json")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("x-apisports-key") == "test-key-not-a-secret"
        assert request.url.path == "/leagues"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    with ApiFootballClient(
        api_key="test-key-not-a-secret",
        base_url="https://provider.test",
        transport=transport,
        max_retries=0,
    ) as client:
        envelope = client.get("/leagues", {"current": "true"})
    assert envelope.results == 5
    assert (
        get_metrics().get_counter(
            PROVIDER_REQUESTS_TOTAL,
            labels={"provider": PROVIDER_NAME, "endpoint": "/leagues", "status": "200"},
        )
        == 1.0
    )


def test_client_pagination_fetches_all_pages() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        page = request.url.params.get("page", "1")
        body = {
            "get": "teams",
            "parameters": {"league": "39", "page": page},
            "errors": [],
            "results": 1,
            "paging": {"current": int(page), "total": 2},
            "response": [{"team": {"id": int(page), "name": f"T{page}", "code": None}}],
        }
        return httpx.Response(
            200,
            json=body,
            headers={"x-ratelimit-requests-remaining": "99", "x-ratelimit-requests-limit": "100"},
        )

    with ApiFootballClient(
        api_key="test-key-not-a-secret",
        base_url="https://provider.test",
        transport=httpx.MockTransport(handler),
        max_retries=0,
    ) as client:
        envelope = client.get("/teams", {"league": 39})
    assert len(calls) == 2
    assert envelope.results == 2
    clubs = map_clubs(envelope)
    assert {c.provider_id for c in clubs} == {1, 2}


def test_client_retries_on_429_then_succeeds() -> None:
    attempts = {"n": 0}
    payload = _load("reference/leagues.json")

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=payload)

    with ApiFootballClient(
        api_key="test-key-not-a-secret",
        base_url="https://provider.test",
        transport=httpx.MockTransport(handler),
        max_retries=2,
        retry_backoff_seconds=0,
        rate_limit_pause_seconds=0.01,
        requests_per_minute=1000,
    ) as client:
        envelope = client.get("/leagues")
    assert envelope.results == 5
    assert attempts["n"] == 2
    assert (
        get_metrics().get_counter(
            PROVIDER_RETRIES_TOTAL,
            labels={"provider": PROVIDER_NAME, "endpoint": "/leagues"},
        )
        == 1.0
    )


def test_client_auth_error_no_retry() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    with (
        ApiFootballClient(
            api_key="test-key-not-a-secret",
            base_url="https://provider.test",
            transport=httpx.MockTransport(handler),
            max_retries=3,
            retry_backoff_seconds=0,
        ) as client,
        pytest.raises(ProviderAuthError),
    ):
        client.get("/leagues")


def test_client_exhausted_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"})

    with (
        ApiFootballClient(
            api_key="test-key-not-a-secret",
            base_url="https://provider.test",
            transport=httpx.MockTransport(handler),
            max_retries=0,
            retry_backoff_seconds=0,
            rate_limit_pause_seconds=0,
            max_rate_limit_pauses=1,
            requests_per_minute=1000,
        ) as client,
        pytest.raises(ProviderRateLimitError),
    ):
        client.get("/status")


def test_client_pauses_on_envelope_rate_limit_then_succeeds() -> None:
    attempts = {"n": 0}
    payload = _load("reference/leagues.json")

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            return httpx.Response(
                200,
                json={
                    "get": "players/squads",
                    "parameters": {},
                    "errors": {"rateLimit": "Too many requests."},
                    "results": 0,
                    "paging": {"current": 1, "total": 1},
                    "response": [],
                },
            )
        return httpx.Response(200, json=payload)

    with ApiFootballClient(
        api_key="test-key-not-a-secret",
        base_url="https://provider.test",
        transport=httpx.MockTransport(handler),
        rate_limit_pause_seconds=0,
        requests_per_minute=1000,
    ) as client:
        envelope = client.get("/leagues")
    assert envelope.results == 5
    assert attempts["n"] == 2


def test_minute_rate_limiter_waits_when_window_full(monkeypatch: pytest.MonkeyPatch) -> None:
    from sports_data.provider.throttle import MinuteRateLimiter

    clock = {"t": 0.0}
    sleeps: list[float] = []

    def fake_monotonic() -> float:
        return clock["t"]

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock["t"] += seconds

    limiter = MinuteRateLimiter(
        max_per_minute=2,
        window_seconds=60.0,
        sleep_fn=fake_sleep,
        monotonic_fn=fake_monotonic,
    )
    assert limiter.acquire() == 0.0
    clock["t"] += 1.0
    assert limiter.acquire() == 0.0
    clock["t"] += 1.0
    waited = limiter.acquire()
    assert waited > 0
    assert sleeps
    assert sleeps[0] == pytest.approx(58.05, abs=0.2)


def test_client_http_500_exhausted() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    with (
        ApiFootballClient(
            api_key="test-key-not-a-secret",
            base_url="https://provider.test",
            transport=httpx.MockTransport(handler),
            max_retries=0,
        ) as client,
        pytest.raises(ProviderHttpError) as exc,
    ):
        client.get("/status")
    assert exc.value.status_code == 503
