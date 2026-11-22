"""Import dello storico stagioni dal fornitore (1.3), con il client vero e il trasporto finto.

Nessuna chiamata reale: ``httpx.MockTransport`` risponde come API-Football ``/players``
(pagine di campionato con ``paging.total``, poi ricerca per id dei calciatori mancanti).
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from database.enums import FantasyRole
from leagues.models.competition import Competition
from sports_data.catalog.models import Club
from sports_data.listone.models import RoleAssignment
from sports_data.provider.client import ApiFootballClient
from sports_data.provider.models import ProviderSnapshot
from sports_data.provider.throttle import MinuteRateLimiter
from sports_data.roster.models import Athlete
from sports_data.season_stats.models import AthleteSeasonImportFetch, AthleteSeasonStat
from sports_data.season_stats.provider_import import (
    ESTIMATED_PAGES_PER_COMPETITION_SEASON,
    STOP_MAX_CALLS,
    STOP_QUOTA_RESERVE,
    estimate_import,
    run_provider_import,
)

SERIE_A = 135
PREMIER = 39
COMPETITIONS = (SERIE_A, PREMIER)
CLUB_KNOWN = 917_001  # esiste da noi
CLUB_OTHER = 917_002  # esiste da noi
CLUB_FOREIGN = 917_099  # campionato estero: da noi non c'è, resta il nome

# Calciatori del listone 2026/27 (provider id).
ROSSI = 917_101  # Serie A in entrambe le stagioni
BIANCHI = 917_102  # 2025/26: due club (trasferimento a metà stagione)
VERDI = 917_103  # 2025/26 da un altro campionato, media del fornitore assente
NERI = 917_104  # nessun dato in nessuna stagione
NOT_IN_LISTONE = 917_199


def _stat(
    *,
    team: int,
    team_name: str,
    league: int,
    league_name: str,
    season: int,
    apps: int | None,
    minutes: int | None,
    rating: str | None,
    goals: int | None = 0,
    assists: int | None = None,
    conceded: int | None = 0,
    saves: int | None = None,
    pen_saved: int | None = 0,
    yellow: int | None = 0,
    red: int | None = 0,
) -> dict[str, Any]:
    return {
        "team": {"id": team, "name": team_name, "logo": "x"},
        "league": {"id": league, "name": league_name, "country": "x", "season": season},
        "games": {
            "appearences": apps,
            "lineups": apps,
            "minutes": minutes,
            "number": None,
            "position": "Attacker",
            "rating": rating,
            "captain": False,
        },
        "substitutes": {"in": 0, "out": 0, "bench": 0},
        "goals": {"total": goals, "conceded": conceded, "assists": assists, "saves": saves},
        "cards": {"yellow": yellow, "yellowred": 0, "red": red},
        "penalty": {"won": None, "commited": None, "scored": 0, "missed": 0, "saved": pen_saved},
    }


def _player(provider_id: int, name: str, *stats: dict[str, Any]) -> dict[str, Any]:
    return {"player": {"id": provider_id, "name": name}, "statistics": list(stats)}


def _envelope(params: dict[str, str], response: list[Any], *, page: int, total: int) -> dict:
    return {
        "get": "players",
        "parameters": params,
        "errors": [],
        "results": len(response),
        "paging": {"current": page, "total": total},
        "response": response,
    }


class FakeProvider:
    """Risponde a ``/players`` come API-Football; conta le chiamate."""

    def __init__(self, *, daily_remaining: int | None = None, daily_limit: int = 7500) -> None:
        self.calls: list[dict[str, str]] = []
        self.daily_remaining = daily_remaining
        self.daily_limit = daily_limit

    def league_page(self, league: int, season: int, page: int) -> tuple[list[Any], int]:
        if league != SERIE_A:
            return [], 1
        if season == 2025:
            pages = {
                1: [
                    _player(
                        ROSSI,
                        "M. Rossi",
                        _stat(
                            team=CLUB_KNOWN,
                            team_name="Club Noto",
                            league=SERIE_A,
                            league_name="Serie A",
                            season=2025,
                            apps=34,
                            minutes=2900,
                            rating="7.212500",
                            goals=18,
                            assists=6,
                            yellow=4,
                            red=1,
                        ),
                    ),
                    _player(
                        BIANCHI,
                        "L. Bianchi",
                        _stat(
                            team=CLUB_KNOWN,
                            team_name="Club Noto",
                            league=SERIE_A,
                            league_name="Serie A",
                            season=2025,
                            apps=10,
                            minutes=700,
                            rating="6.500000",
                        ),
                        _stat(
                            team=CLUB_OTHER,
                            team_name="Altro Club",
                            league=SERIE_A,
                            league_name="Serie A",
                            season=2025,
                            apps=15,
                            minutes=1200,
                            rating="7.000000",
                        ),
                    ),
                ],
                2: [
                    _player(
                        NOT_IN_LISTONE,
                        "Andato Via",
                        _stat(
                            team=CLUB_KNOWN,
                            team_name="Club Noto",
                            league=SERIE_A,
                            league_name="Serie A",
                            season=2025,
                            apps=5,
                            minutes=300,
                            rating="6.1",
                        ),
                    )
                ],
            }
            return pages.get(page, []), 2
        if season == 2024:
            return [
                _player(
                    ROSSI,
                    "M. Rossi",
                    _stat(
                        team=CLUB_KNOWN,
                        team_name="Club Noto",
                        league=SERIE_A,
                        league_name="Serie A",
                        season=2024,
                        apps=30,
                        minutes=2500,
                        rating="6.95",
                        goals=12,
                    ),
                )
            ], 1
        return [], 1

    def by_id(self, provider_id: int, season: int) -> list[Any]:
        if provider_id == VERDI and season == 2025:
            return [
                _player(
                    VERDI,
                    "G. Verdi",
                    _stat(
                        team=CLUB_FOREIGN,
                        team_name="Club Estero",
                        league=88,
                        league_name="Eredivisie",
                        season=2025,
                        apps=3,
                        minutes=40,
                        rating=None,
                        conceded=None,
                    ),
                )
            ]
        return []

    def handler(self, request: httpx.Request) -> httpx.Response:
        params = dict(request.url.params)
        self.calls.append(params)
        assert request.url.path == "/players"
        season = int(params["season"])
        if "league" in params:
            page = int(params.get("page", "1"))
            response, total = self.league_page(int(params["league"]), season, page)
            body = _envelope(params, response, page=page, total=total)
        else:
            response = self.by_id(int(params["id"]), season)
            body = _envelope(params, response, page=1, total=1)
        headers = {}
        if self.daily_remaining is not None:
            headers = {
                "x-ratelimit-requests-limit": str(self.daily_limit),
                "x-ratelimit-requests-remaining": str(self.daily_remaining),
            }
        return httpx.Response(200, json=body, headers=headers)

    def client(self) -> ApiFootballClient:
        return ApiFootballClient(
            api_key="test-key",
            transport=httpx.MockTransport(self.handler),
            max_retries=0,
            rate_limiter=MinuteRateLimiter(max_per_minute=100_000),
        )


@pytest.fixture(autouse=True)
def seeded(session: Session) -> dict[str, Any]:
    session.execute(delete(AthleteSeasonImportFetch))
    session.execute(delete(AthleteSeasonStat))
    session.execute(delete(RoleAssignment).where(RoleAssignment.season_year == 2026))
    session.execute(delete(Athlete).where(Athlete.provider_id.between(917_000, 917_999)))
    session.execute(delete(Club).where(Club.provider_id.between(917_000, 917_999)))
    known = Club(provider_id=CLUB_KNOWN, name="Club Noto")
    other = Club(provider_id=CLUB_OTHER, name="Altro Club")
    session.add_all([known, other])
    athletes = {}
    for provider_id, name, role in (
        (ROSSI, "Mario Rossi", FantasyRole.A),
        (BIANCHI, "Luca Bianchi", FantasyRole.C),
        (VERDI, "Gino Verdi", FantasyRole.D),
        (NERI, "Ugo Neri", FantasyRole.P),
    ):
        athlete = Athlete(provider_id=provider_id, canonical_name=name)
        session.add(athlete)
        session.flush()
        session.add(
            RoleAssignment(
                athlete_id=athlete.id,
                season_year=2026,
                role=role,
                mapping_version="v1.0.0",
            )
        )
        athletes[provider_id] = athlete
    session.flush()
    return {"athletes": athletes, "known": known, "other": other}


def _rows(session: Session, provider_id: int, season: int) -> list[AthleteSeasonStat]:
    return list(
        session.scalars(
            select(AthleteSeasonStat)
            .where(
                AthleteSeasonStat.athlete_provider_id == provider_id,
                AthleteSeasonStat.season_year == season,
            )
            .order_by(AthleteSeasonStat.club_provider_id)
        ).all()
    )


def _count(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def test_dry_run_counts_without_calling_the_provider(session: Session) -> None:
    provider = FakeProvider()
    estimate = estimate_import(session, current_season_year=2026, competitions=COMPETITIONS)

    assert provider.calls == []
    assert [item.season_year for item in estimate.seasons] == [2025, 2024]
    assert [item.label for item in estimate.seasons] == ["25/26", "24/25"]
    first = estimate.seasons[0]
    assert first.league_pages_exact is False
    assert first.league_pages_remaining == ESTIMATED_PAGES_PER_COMPETITION_SEASON * 2
    assert first.listone_athletes == 4
    assert first.athletes_to_fill_exact is False
    assert first.athletes_to_fill == 1  # 25% di 4 calciatori, stima prima delle pagine


def test_import_pages_fills_missing_athletes_and_stores_snapshots(
    session: Session, seeded: dict[str, Any]
) -> None:
    provider = FakeProvider()
    snapshots_before = _count(session, ProviderSnapshot)

    result = run_provider_import(
        session, provider.client(), current_season_year=2026, competitions=COMPETITIONS
    )

    assert result.completed
    assert result.seasons == (2025, 2024)
    # Pagine: Serie A 2025 (2) + Premier 2025 (1) + Serie A 2024 (1) + Premier 2024 (1) = 5.
    league_calls = [call for call in provider.calls if "league" in call]
    assert len(league_calls) == 5
    assert {"league": "135", "season": "2025", "page": "2"} in league_calls
    # Mancanti: 2025 → Verdi e Neri (Rossi e Bianchi già nelle pagine); 2024 → tutti tranne
    # Rossi. Uno per chiamata, con id e stagione.
    id_calls = sorted(
        (int(call["id"]), int(call["season"])) for call in provider.calls if "id" in call
    )
    assert id_calls == sorted(
        [(VERDI, 2025), (NERI, 2025), (BIANCHI, 2024), (VERDI, 2024), (NERI, 2024)]
    )
    assert result.counters.calls == 10
    assert result.counters.league_pages == 5
    assert result.counters.athletes_checked == 5
    assert result.counters.athletes_found == 1
    assert _count(session, ProviderSnapshot) - snapshots_before == 10

    rossi = _rows(session, ROSSI, 2025)
    assert len(rossi) == 1
    row = rossi[0]
    assert row.source == "provider"
    assert row.athlete_id == seeded["athletes"][ROSSI].id
    assert row.club_id == seeded["known"].id
    assert row.competition_id == session.scalar(
        select(Competition.id).where(Competition.provider_id == SERIE_A)
    )
    assert (row.appearances, row.minutes, row.goals, row.assists) == (34, 2900, 18, 6)
    assert (row.yellow_cards, row.red_cards, row.goals_conceded, row.penalties_saved) == (
        4,
        1,
        0,
        0,
    )
    assert row.rating == pytest.approx(7.2125)
    assert row.clean_sheets is None  # non c'è nell'aggregato del fornitore
    assert row.snapshot_id is not None

    # Trasferimento a metà stagione: due righe, una per club.
    bianchi = _rows(session, BIANCHI, 2025)
    assert [(r.club_provider_id, r.appearances) for r in bianchi] == [
        (CLUB_KNOWN, 10),
        (CLUB_OTHER, 15),
    ]

    # Arrivato da un campionato che da noi non c'è: id nostri vuoti, nomi tenuti, media nulla.
    verdi = _rows(session, VERDI, 2025)
    assert len(verdi) == 1
    assert verdi[0].club_id is None and verdi[0].club_name == "Club Estero"
    assert verdi[0].competition_id is None and verdi[0].competition_name == "Eredivisie"
    assert verdi[0].rating is None
    assert verdi[0].goals_conceded is None

    # Anche chi non è nel listone resta salvato (con i dati grezzi del fornitore).
    assert len(_rows(session, NOT_IN_LISTONE, 2025)) == 1
    assert _rows(session, NERI, 2025) == []

    # Dopo l'import non resta niente da scaricare.
    remaining = estimate_import(session, current_season_year=2026, competitions=COMPETITIONS)
    assert remaining.estimated_calls == 0
    assert all(item.league_pages_exact for item in remaining.seasons)


def test_rerun_is_idempotent_and_makes_no_calls(session: Session) -> None:
    first = FakeProvider()
    run_provider_import(
        session, first.client(), current_season_year=2026, competitions=COMPETITIONS
    )
    rows = _count(session, AthleteSeasonStat)
    snapshots = _count(session, ProviderSnapshot)

    second = FakeProvider()
    again = run_provider_import(
        session, second.client(), current_season_year=2026, competitions=COMPETITIONS
    )

    assert second.calls == []
    assert again.completed
    assert again.counters.calls == 0
    assert _count(session, AthleteSeasonStat) == rows
    assert _count(session, ProviderSnapshot) == snapshots


def test_stops_at_max_calls_and_resumes_where_it_left_off(session: Session) -> None:
    first = FakeProvider()
    partial = run_provider_import(
        session,
        first.client(),
        current_season_year=2026,
        max_calls=3,
        competitions=COMPETITIONS,
    )
    assert partial.stopped_reason == STOP_MAX_CALLS
    assert len(first.calls) == 3

    second = FakeProvider()
    resumed = run_provider_import(
        session, second.client(), current_season_year=2026, competitions=COMPETITIONS
    )
    assert resumed.completed
    # Le 3 chiamate fatte non si ripetono: in tutto 10, come senza interruzione.
    assert len(first.calls) + len(second.calls) == 10
    assert not any(call in second.calls for call in first.calls)
    assert len(_rows(session, ROSSI, 2024)) == 1


def test_stops_when_daily_quota_reaches_the_reserve(session: Session) -> None:
    provider = FakeProvider(daily_remaining=500, daily_limit=7500)  # 6,7% < 15%
    result = run_provider_import(
        session, provider.client(), current_season_year=2026, competitions=COMPETITIONS
    )
    assert result.stopped_reason == STOP_QUOTA_RESERVE
    assert len(provider.calls) == 1
    # La pagina scaricata è salvata: rilanciando si riparte dalla seconda.
    assert _count(session, AthleteSeasonImportFetch) == 1
