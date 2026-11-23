# ruff: noqa: F811
"""Pannello operatore: «Dettaglio del Valore» di un calciatore (1.4).

``GET /admin/listone/valori/{athleteId}?seasonYear=…&leagueId=…``: solo operatore
(``global:operate``), a chiunque altro 403. Legge la riga dell'ultimo ricalcolo e ne spiega ogni
passaggio: righe contate ed escluse di ogni stagione, media del ruolo, media ristretta,
percentile fra i calciatori del ruolo, pesi, p, curva e crediti al budget della lega.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from tests.integration.fantasy_lineups.test_trade_overflow_lineup import (  # noqa: F401
    _headers,
    _register_and_login,
    competition_ids,
    db_session,
)
from tests.integration.fantasy_turns.test_fantasy_turns import _promote_to_operator

from database.enums import FantasyRole
from leagues.models.league_rules import LeagueRules
from market.valuation import (
    MISSING_SEASON_INDEX,
    base_reference_value,
    credits_for_budget,
    value_curve,
)
from market.valuation_models import AthleteMarketValue
from market.valuation_service import VALUATION_VERSION, refresh_market_values
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete
from sports_data.season_stats.models import AthleteSeasonStat, ProviderCompetitionType

SEASON = 2026
DETAIL_URL = "/admin/listone/valori"
PREMIER_LEAGUE = 39
LIGUE_1 = 61
CHAMPIONS_LEAGUE = 2

SUBJECT = 931_001  # il «Donnarumma» del test: 7,03 in Premier, 6,86 in Ligue 1, più Champions
OTHERS = (931_002, 931_003, 931_004)
LATE = 931_009  # nel listone, ma entrato dopo l'ultimo ricalcolo


def _row(
    athlete: Athlete,
    *,
    season: int,
    competition: int,
    name: str,
    rating: float | None,
    apps: int,
    club: str = "Club Storico",
) -> AthleteSeasonStat:
    return AthleteSeasonStat(
        athlete_provider_id=athlete.provider_id,
        athlete_id=athlete.id,
        season_year=season,
        source="provider",
        club_provider_id=931_500,
        club_name=club,
        competition_provider_id=competition,
        competition_name=name,
        appearances=apps,
        minutes=apps * 90,
        rating=rating,
    )


@pytest.fixture
def goalkeepers(db_session: Session) -> dict[int, Athlete]:
    """Quattro portieri con storico (2025/26 Premier League, 2024/25 Ligue 1) e uno senza riga
    di Valore. Il database del modulo resta fra un test e l'altro: si riparte da zero."""
    db_session.execute(delete(AthleteMarketValue))
    db_session.execute(delete(AthleteSeasonStat))
    db_session.execute(delete(ProviderCompetitionType))
    db_session.execute(delete(RoleAssignment).where(RoleAssignment.season_year == SEASON))
    athletes: dict[int, Athlete] = {}
    for provider_id in (SUBJECT, *OTHERS, LATE):
        athlete = db_session.scalar(select(Athlete).where(Athlete.provider_id == provider_id))
        if athlete is None:
            athlete = Athlete(provider_id=provider_id, canonical_name=f"Portiere {provider_id}")
            db_session.add(athlete)
            db_session.flush()
        athletes[provider_id] = athlete
        if provider_id != LATE:
            db_session.add(
                RoleAssignment(
                    athlete_id=athlete.id,
                    season_year=SEASON,
                    role=FantasyRole.P,
                    mapping_version="v1.0.0",
                )
            )
    subject = athletes[SUBJECT]
    db_session.add(
        ProviderCompetitionType(
            provider_id=CHAMPIONS_LEAGUE,
            type="cup",
            name="UEFA Champions League",
            fetched_at=datetime.now(UTC),
        )
    )
    db_session.add_all(
        [
            _row(
                subject,
                season=2025,
                competition=PREMIER_LEAGUE,
                name="Premier League",
                rating=7.03,
                apps=34,
                club="Manchester City",
            ),
            _row(
                subject,
                season=2025,
                competition=CHAMPIONS_LEAGUE,
                name="UEFA Champions League",
                rating=7.4,
                apps=10,
                club="Manchester City",
            ),
            _row(
                subject,
                season=2024,
                competition=LIGUE_1,
                name="Ligue 1",
                rating=6.86,
                apps=36,
                club="Paris Saint Germain",
            ),
        ]
    )
    for index, provider_id in enumerate(OTHERS):
        athlete = athletes[provider_id]
        db_session.add_all(
            [
                _row(
                    athlete,
                    season=2025,
                    competition=PREMIER_LEAGUE,
                    name="Premier League",
                    rating=6.7 + 0.1 * index,
                    apps=30,
                ),
                _row(
                    athlete,
                    season=2024,
                    competition=LIGUE_1,
                    name="Ligue 1",
                    rating=6.8 + 0.05 * index,
                    apps=30,
                ),
            ]
        )
    db_session.commit()
    refresh_market_values(db_session, season_year=SEASON, force=True)
    db_session.add(
        RoleAssignment(
            athlete_id=athletes[LATE].id,
            season_year=SEASON,
            role=FantasyRole.P,
            mapping_version="v1.0.0",
        )
    )
    db_session.commit()
    return athletes


def _operator(client: TestClient, db_session: Session, email: str) -> str:
    token, user_id = _register_and_login(client, email)
    _promote_to_operator(db_session, user_id)
    return token


def _url(athlete_id: object, **params: object) -> str:
    query = "&".join(f"{key}={value}" for key, value in {"seasonYear": SEASON, **params}.items())
    return f"{DETAIL_URL}/{athlete_id}?{query}"


def test_only_operators_see_the_detail(
    client: TestClient, db_session: Session, goalkeepers: dict[int, Athlete]
) -> None:
    token, _ = _register_and_login(client, "valore.utente@example.com")
    url = _url(goalkeepers[SUBJECT].id)
    assert client.get(url, headers=_headers(token)).status_code == 403
    assert client.get(url).status_code == 401


def test_detail_explains_every_step(
    client: TestClient, db_session: Session, goalkeepers: dict[int, Athlete]
) -> None:
    token = _operator(client, db_session, "valore.operatore@example.com")

    response = client.get(_url(goalkeepers[SUBJECT].id), headers=_headers(token))

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["status"] == "computed"
    assert body["version"] == VALUATION_VERSION
    assert body["canonicalName"] == f"Portiere {SUBJECT}"
    assert body["role"] == "P"
    assert body["seasonLabel"] == "26/27"
    assert body["computedAt"] is not None
    assert [season["seasonLabel"] for season in body["seasons"]] == ["26/27", "25/26", "24/25"]
    current, previous, two_ago = body["seasons"]

    # Stagione in corso senza voti: peso 0.
    assert current["hasData"] is False
    assert current["weight"] == 0 and current["contribution"] == 0
    assert current["source"] is None

    # 2025/26: fornitore, solo la Premier League conta (Champions esclusa).
    assert previous["source"] == "provider"
    assert previous["competitions"] == ["Premier League"]
    assert previous["rows"] == [
        {
            "competition": "Premier League",
            "club": "Manchester City",
            "appearances": 34,
            "average": 7.03,
            "kind": "league",
        }
    ]
    assert [(row["competition"], row["kind"]) for row in previous["excluded"]] == [
        ("UEFA Champions League", "cup")
    ]
    assert previous["appearances"] == 34
    assert previous["average"] == pytest.approx(7.03)
    role_average = (7.03 * 34 + (6.7 + 6.8 + 6.9) * 30) / (34 + 90)
    assert previous["roleAverage"] == pytest.approx(role_average, abs=1e-4)
    assert previous["shrunkAverage"] == pytest.approx((34 * 7.03 + 8 * role_average) / 42, abs=1e-4)
    assert previous["poolSize"] == 4
    assert previous["rank"] == 1
    assert previous["percentile"] == pytest.approx(0.875)
    assert previous["weight"] == pytest.approx(0.6)

    # 2024/25: Ligue 1, secondo dei quattro portieri.
    assert two_ago["competitions"] == ["Ligue 1"]
    assert two_ago["rank"] == 2
    assert two_ago["weight"] == pytest.approx(0.4)

    # Si rifà il numero dai passaggi: p = somma dei contributi, poi la curva del ruolo.
    p = sum(season["contribution"] for season in body["seasons"])
    assert body["valueIndex"] == pytest.approx(p, abs=1e-3)
    assert body["roleTop"] == 30
    assert body["referenceValue"] == pytest.approx(value_curve(body["valueIndex"], "P"), abs=1e-3)
    assert body["referenceCredits"] == credits_for_budget(body["referenceValue"], 1000)
    assert body["referenceBudget"] == 1000
    assert body["baseReferenceValue"] == pytest.approx(base_reference_value("P"), abs=1e-3)
    assert body["missingSeasonIndex"] == MISSING_SEASON_INDEX
    assert body["league"] is None


def test_detail_with_league_budget(
    client: TestClient,
    db_session: Session,
    goalkeepers: dict[int, Athlete],
    competition_ids: list[str],
) -> None:
    token = _operator(client, db_session, "valore.lega@example.com")
    created = client.post(
        "/leagues",
        headers=_headers(token),
        json={"name": "Lega Valore", "seasonYear": SEASON, "competitionIds": competition_ids},
    )
    assert created.status_code == 201, created.json()
    league_id = created.json()["id"]
    rules = db_session.scalar(select(LeagueRules).where(LeagueRules.league_id == UUID(league_id)))
    assert rules is not None
    rules.total_credits = 500
    db_session.commit()

    body = client.get(
        _url(goalkeepers[SUBJECT].id, leagueId=league_id), headers=_headers(token)
    ).json()

    assert body["league"] == {
        "leagueId": league_id,
        "leagueName": "Lega Valore",
        "budget": 500,
        "credits": credits_for_budget(body["referenceValue"], 500),
    }
    missing = client.get(_url(goalkeepers[SUBJECT].id, leagueId=uuid4()), headers=_headers(token))
    assert missing.status_code == 404
    assert missing.json()["code"] == "market_value_league_not_found"


def test_not_computed_outdated_and_unknown(
    client: TestClient, db_session: Session, goalkeepers: dict[int, Athlete]
) -> None:
    token = _operator(client, db_session, "valore.casi@example.com")

    # Entrato nel listone dopo l'ultimo ricalcolo: valore base del ruolo.
    late = client.get(_url(goalkeepers[LATE].id), headers=_headers(token)).json()
    assert late["status"] == "not_computed"
    assert late["valueIndex"] == pytest.approx(MISSING_SEASON_INDEX)
    assert late["referenceCredits"] == credits_for_budget(base_reference_value("P"), 1000)
    assert [season["hasData"] for season in late["seasons"]] == [False, False, False]

    # Riga scritta prima della 1.4 (solo pesi e percentili): si vede quello che c'è.
    row = db_session.scalar(
        select(AthleteMarketValue).where(AthleteMarketValue.athlete_id == goalkeepers[SUBJECT].id)
    )
    assert row is not None
    row.components_json = {
        "weights": {"current": 0.0, "previous": 0.6, "twoSeasonsAgo": 0.4},
        "percentiles": {"current": None, "previous": 0.875, "twoSeasonsAgo": 0.625},
        "hasHistory": True,
    }
    db_session.commit()
    old = client.get(_url(goalkeepers[SUBJECT].id), headers=_headers(token)).json()
    assert old["status"] == "outdated"
    assert old["version"] is None
    assert [season["percentile"] for season in old["seasons"]] == [None, 0.875, 0.625]
    assert old["seasons"][1]["contribution"] == pytest.approx(0.525)
    assert old["seasons"][1]["rows"] == []

    # Fuori dal listone della stagione.
    assert client.get(_url(uuid4()), headers=_headers(token)).status_code == 404
    other_season = client.get(
        f"{DETAIL_URL}/{goalkeepers[SUBJECT].id}?seasonYear=2025", headers=_headers(token)
    )
    assert other_season.status_code == 404
    assert other_season.json()["code"] == "market_value_athlete_not_found"
