# ruff: noqa: F811
"""Pannello operatore: «Importa lo storico» dal fornitore e ricalcolo del Valore (1.3).

Solo operatore (``global:operate``): a chiunque altro 403. ``dryRun`` dà il conto senza
chiamare il fornitore; il job (Celery in modalità eager nei test) usa un client finto.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _register_and_login,
    db_session,
)
from tests.integration.fantasy_turns.test_fantasy_turns import _promote_to_operator

from database.enums import FantasyRole
from market.valuation_models import AthleteMarketValue
from sports_data.listone.models import RoleAssignment
from sports_data.provider.client import ApiFootballClient
from sports_data.provider.throttle import MinuteRateLimiter
from sports_data.roster.models import Athlete
from sports_data.season_stats.models import AthleteSeasonImportFetch, AthleteSeasonStat

IMPORT_URL = "/admin/listone/storico"
REFRESH_URL = "/admin/listone/valori/ricalcola"
IN_PAGES = 919_001
FILLED = 919_002


def _player(provider_id: int, season: int, league: int, rating: str | None) -> dict[str, Any]:
    return {
        "player": {"id": provider_id, "name": f"P{provider_id}"},
        "statistics": [
            {
                "team": {"id": 919_500, "name": "Club Storico"},
                "league": {"id": league, "name": "Lega", "season": season},
                "games": {"appearences": 20, "lineups": 18, "minutes": 1600, "rating": rating},
                "goals": {"total": 4, "assists": 2, "conceded": 0, "saves": None},
                "cards": {"yellow": 3, "red": 0},
                "penalty": {"saved": 0},
            }
        ],
    }


class _Provider:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        self.calls.append(params)
        season = int(params["season"])
        response: list[Any] = []
        if params.get("league") == "135":
            response = [_player(IN_PAGES, season, 135, "6.9")]
        elif params.get("id") == str(FILLED) and season == 2025:
            response = [_player(FILLED, season, 94, None)]
        body = {
            "get": "players",
            "parameters": params,
            "errors": [],
            "results": len(response),
            "paging": {"current": 1, "total": 1},
            "response": response,
        }
        return httpx.Response(200, json=body)

    def client(self) -> ApiFootballClient:
        return ApiFootballClient(
            api_key="test-key",
            transport=httpx.MockTransport(self.handler),
            max_retries=0,
            rate_limiter=MinuteRateLimiter(max_per_minute=100_000),
        )


@pytest.fixture
def listone(db_session: Session) -> None:
    """Due calciatori nel listone 2026 e nessuno storico importato (il database del modulo
    resta fra un test e l'altro: si riparte da zero)."""
    db_session.execute(delete(AthleteSeasonImportFetch))
    db_session.execute(delete(AthleteSeasonStat))
    for provider_id, role in ((IN_PAGES, FantasyRole.A), (FILLED, FantasyRole.D)):
        athlete = db_session.scalar(select(Athlete).where(Athlete.provider_id == provider_id))
        if athlete is not None:
            continue
        athlete = Athlete(provider_id=provider_id, canonical_name=f"Storico {provider_id}")
        db_session.add(athlete)
        db_session.flush()
        db_session.add(
            RoleAssignment(
                athlete_id=athlete.id, season_year=2026, role=role, mapping_version="v1.0.0"
            )
        )
    db_session.commit()


def _operator(client: TestClient, db_session: Session, email: str) -> str:
    token, user_id = _register_and_login(client, email)
    _promote_to_operator(db_session, user_id)
    return token


def test_non_operators_get_403(client: TestClient, db_session: Session) -> None:
    token, _ = _register_and_login(client, "storico.utente@example.com")
    headers = _headers(token)

    responses = [
        client.post(IMPORT_URL, headers=headers, json={"seasonYear": 2026}),
        client.post(IMPORT_URL, headers=headers, json={"seasonYear": 2026, "dryRun": False}),
        client.get(IMPORT_URL, headers=headers),
        client.get(f"{IMPORT_URL}/{uuid4()}", headers=headers),
        client.post(REFRESH_URL, headers=headers, json={"seasonYear": 2026}),
    ]
    assert [response.status_code for response in responses] == [403] * len(responses)
    assert client.post(IMPORT_URL, json={"seasonYear": 2026}).status_code == 401


def test_dry_run_counts_calls_without_calling_the_provider(
    client: TestClient,
    db_session: Session,
    listone: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_provider(_settings: object) -> None:
        raise AssertionError("il conto non deve chiamare il fornitore")

    monkeypatch.setattr("admin.season_history_service.build_client_from_settings", no_provider)
    token = _operator(client, db_session, "storico.conta@example.com")

    response = client.post(IMPORT_URL, headers=_headers(token), json={"seasonYear": 2026})

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["dryRun"] is True
    assert body["job"] is None
    estimate = body["estimate"]
    assert estimate["seasonYear"] == 2026
    assert [season["seasonLabel"] for season in estimate["seasons"]] == ["25/26", "24/25"]
    # 5 campionati × 40 pagine stimate + 25% del listone da cercare, per stagione.
    assert estimate["seasons"][0]["leaguePagesRemaining"] == 200
    assert estimate["seasons"][0]["leaguePagesExact"] is False
    assert estimate["estimatedCalls"] >= 400
    assert estimate["requestsPerMinute"] >= 1
    assert estimate["estimatedMinutes"] >= 1


def test_import_job_runs_with_progress_then_rerun_is_free(
    client: TestClient,
    db_session: Session,
    listone: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _Provider()
    monkeypatch.setattr(
        "admin.season_history_service.build_client_from_settings",
        lambda _settings: provider.client(),
    )
    token = _operator(client, db_session, "storico.job@example.com")

    started = client.post(
        IMPORT_URL, headers=_headers(token), json={"seasonYear": 2026, "dryRun": False}
    )

    assert started.status_code == 200, started.json()
    job = started.json()["job"]
    assert job is not None and job["status"] == "queued"
    progress = client.get(f"{IMPORT_URL}/{job['jobId']}", headers=_headers(token))
    assert progress.status_code == 200
    body = progress.json()
    assert body["status"] == "completed", body
    result = body["result"]
    # 5 campionati × 2 stagioni (una pagina ciascuno) + il calciatore mancante × 2 stagioni.
    assert result["leaguePages"] == 10
    assert result["athletesChecked"] == 2
    assert result["athletesFound"] == 1
    assert result["calls"] == 12
    assert result["stoppedReason"] is None
    assert result["remaining"]["estimatedCalls"] == 0
    assert result["marketValues"]["athletesValued"] >= 2
    assert client.get(IMPORT_URL, headers=_headers(token)).json() is None  # nessun job attivo

    db_session.expire_all()
    rows = db_session.scalars(
        select(AthleteSeasonStat).where(AthleteSeasonStat.athlete_provider_id == FILLED)
    ).all()
    assert [(row.season_year, row.rating, row.competition_provider_id) for row in rows] == [
        (2025, None, 94)
    ]
    value = db_session.scalar(
        select(AthleteMarketValue).join(Athlete).where(Athlete.provider_id == IN_PAGES)
    )
    assert value is not None
    assert value.season_average == pytest.approx(6.9)
    assert value.season_average_year == 2025 and value.season_average_is_current is False

    fetches = db_session.scalar(select(func.count()).select_from(AthleteSeasonImportFetch))
    again = client.post(
        IMPORT_URL, headers=_headers(token), json={"seasonYear": 2026, "dryRun": False}
    )
    second = client.get(f"{IMPORT_URL}/{again.json()['job']['jobId']}", headers=_headers(token))
    assert second.json()["status"] == "completed"
    assert second.json()["result"]["calls"] == 0
    assert len(provider.calls) == 12
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(AthleteSeasonImportFetch)) == fetches


def test_missing_provider_key_fails_the_job_with_a_clear_code(
    client: TestClient, db_session: Session, listone: None
) -> None:
    token = _operator(client, db_session, "storico.chiave@example.com")
    started = client.post(
        IMPORT_URL, headers=_headers(token), json={"seasonYear": 2026, "dryRun": False}
    )
    job_id = started.json()["job"]["jobId"]
    progress = client.get(f"{IMPORT_URL}/{job_id}", headers=_headers(token)).json()
    assert progress["status"] == "failed"
    assert progress["errorCode"] == "provider_key_missing"
    assert client.get(f"{IMPORT_URL}/{uuid4()}", headers=_headers(token)).status_code == 404


def test_operator_refresh_skips_when_nothing_changed(
    client: TestClient, db_session: Session, listone: None
) -> None:
    token = _operator(client, db_session, "storico.ricalcolo@example.com")
    first = client.post(REFRESH_URL, headers=_headers(token), json={"seasonYear": 2026})
    assert first.status_code == 200
    assert first.json()["skipped"] is False
    lazy = client.post(
        REFRESH_URL, headers=_headers(token), json={"seasonYear": 2026, "force": False}
    )
    assert lazy.json()["skipped"] is True
