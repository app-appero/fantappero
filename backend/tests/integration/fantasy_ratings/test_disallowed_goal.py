"""Gol o assist annullati (VAR, fuorigioco) non devono lasciare il bonus (QA 28/11).

Caso reale: Venezia–Bologna del 27/11 (turno 12), finita 0–0, con un gol
annullato al 15' e l'assist rimasto nei punti. Qui si usa la partita del corpus
1035055 (West Ham 3–1 Chelsea): il gol di Antonio al 53' con assist di
Ward-Prowse viene annullato in due modi diversi, come può fare il fornitore:

* il gol sparisce dagli eventi alla sincronizzazione successiva;
* il gol resta, ma segue un evento «Var» «Goal Disallowed - offside».

In entrambi i casi i bonus di gol e assist spariscono dopo il ricalcolo; se poi
il gol viene assegnato di nuovo il bonus torna.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from fantasy_ratings.models import PlayerMatchRating
from fantasy_ratings.service import compute_fixture_ratings
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.fixtures.models import (
    Fixture,
    MatchEvent,
    OfficialLineup,
    OfficialLineupEntry,
    PlayerMatchStat,
)
from sports_data.fixtures.sync import FixtureDetailBatch, sync_fixtures
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"
FIXTURE_ID = 1035055
ANTONIO = 18819
WARD_PROWSE = 2938
GOAL_INDEX = 8  # Antonio 53', assist Ward-Prowse


@pytest.fixture(autouse=True)
def clean_tables(session: Session) -> None:
    session.execute(delete(PlayerMatchRating))
    session.execute(delete(OfficialLineupEntry))
    session.execute(delete(OfficialLineup))
    session.execute(delete(PlayerMatchStat))
    session.execute(delete(MatchEvent))
    session.execute(delete(Fixture))
    session.execute(delete(Athlete))
    session.commit()


def _load(name: str) -> dict:
    return json.loads(
        (DATASET / "matches" / "39" / str(FIXTURE_ID) / name).read_text(encoding="utf-8")
    )


def _seed_catalog(session: Session) -> None:
    ref = DATASET / "reference"
    leagues = parse_envelope(
        json.loads((ref / "leagues.json").read_text(encoding="utf-8")),
        endpoint="/leagues",
        http_status=200,
    )
    teams = parse_envelope(
        json.loads((ref / "teams.json").read_text(encoding="utf-8")),
        endpoint="/teams",
        http_status=200,
    )
    sync_catalog(
        session,
        leagues_envelope=leagues,
        teams_batches=[TeamsBatch(envelope=teams, competition_provider_id=39, season_year=2026)],
    )


def _sync(session: Session, *, events: dict, players: dict | None = None) -> Fixture:
    fixtures_env = parse_envelope(_load("fixtures.json"), endpoint="/fixtures", http_status=200)
    batch = FixtureDetailBatch(
        fixture_provider_id=FIXTURE_ID,
        events_envelope=parse_envelope(events, endpoint="/fixtures/events", http_status=200),
        lineups_envelope=parse_envelope(
            _load("fixtures_lineups.json"), endpoint="/fixtures/lineups", http_status=200
        ),
        players_envelope=parse_envelope(
            players or _load("fixtures_players.json"),
            endpoint="/fixtures/players",
            http_status=200,
        ),
    )
    sync_fixtures(session, fixtures_envelopes=[fixtures_env], detail_batches=[batch])
    session.commit()
    return session.execute(select(Fixture).where(Fixture.provider_id == FIXTURE_ID)).scalar_one()


def _players_after_disallowed_goal() -> dict:
    """Statistiche giocatore già corrette dal fornitore: niente gol per Antonio, un assist."""
    players = copy.deepcopy(_load("fixtures_players.json"))
    for team in players["response"]:
        for row in team["players"]:
            goals = row["statistics"][0]["goals"]
            if row["player"]["id"] == ANTONIO:
                goals["total"] = None
            if row["player"]["id"] == WARD_PROWSE:
                goals["assists"] = 1
    return players


def _bonus(session: Session, fixture: Fixture, provider_id: int) -> dict[str, float]:
    compute_fixture_ratings(session, fixture_id=fixture.id)
    session.commit()
    row = session.execute(
        select(PlayerMatchRating).where(
            PlayerMatchRating.fixture_id == fixture.id,
            PlayerMatchRating.athlete_provider_id == provider_id,
        )
    ).scalar_one()
    return {item["id"]: item["contribution"] for item in row.bonus_malus_json}


def _active_scoring(session: Session, fixture: Fixture, kind: str, pid: int) -> list[MatchEvent]:
    return list(
        session.scalars(
            select(MatchEvent).where(
                MatchEvent.fixture_id == fixture.id,
                MatchEvent.scoring_kind == kind,
                MatchEvent.athlete_provider_id == pid,
                MatchEvent.is_active.is_(True),
            )
        ).all()
    )


def _without_goal() -> dict:
    events = copy.deepcopy(_load("fixtures_events.json"))
    removed = events["response"].pop(GOAL_INDEX)
    assert removed["player"]["id"] == ANTONIO and removed["assist"]["id"] == WARD_PROWSE
    return events


def _with_var_disallowed(detail: str = "Goal Disallowed - offside") -> dict:
    events = copy.deepcopy(_load("fixtures_events.json"))
    goal = events["response"][GOAL_INDEX]
    assert goal["player"]["id"] == ANTONIO
    events["response"].insert(
        GOAL_INDEX + 1,
        {
            "assist": {"id": None, "name": None},
            "comments": None,
            "detail": detail,
            "player": {"id": ANTONIO, "name": "Michail Antonio"},
            "team": {"id": 48, "name": "West Ham"},
            "time": {"elapsed": 54, "extra": None},
            "type": "Var",
        },
    )
    return events


def test_goal_and_assist_bonus_before_cancellation(session: Session) -> None:
    _seed_catalog(session)
    session.commit()
    fixture = _sync(session, events=_load("fixtures_events.json"))
    assert _bonus(session, fixture, ANTONIO).get("goal") == 3.0
    assert _bonus(session, fixture, WARD_PROWSE).get("assist") == 2.0


def test_goal_removed_by_provider_retracts_goal_and_assist(session: Session) -> None:
    _seed_catalog(session)
    session.commit()
    fixture = _sync(session, events=_load("fixtures_events.json"))
    assert _bonus(session, fixture, WARD_PROWSE).get("assist") == 2.0

    players = _players_after_disallowed_goal()
    fixture = _sync(session, events=_without_goal(), players=players)
    assert _active_scoring(session, fixture, "goal", ANTONIO) == []
    assert len(_active_scoring(session, fixture, "assist", WARD_PROWSE)) == 1
    assert "goal" not in _bonus(session, fixture, ANTONIO)
    assert _bonus(session, fixture, WARD_PROWSE).get("assist") == 1.0

    # Idempotente: una seconda sincronizzazione identica non cambia nulla.
    fixture = _sync(session, events=_without_goal(), players=players)
    assert _active_scoring(session, fixture, "goal", ANTONIO) == []
    assert _bonus(session, fixture, WARD_PROWSE).get("assist") == 1.0

    # Gol riassegnato (il fornitore lo rimette): il bonus torna.
    fixture = _sync(session, events=_load("fixtures_events.json"))
    assert len(_active_scoring(session, fixture, "goal", ANTONIO)) == 1
    assert _bonus(session, fixture, ANTONIO).get("goal") == 3.0
    assert _bonus(session, fixture, WARD_PROWSE).get("assist") == 2.0


@pytest.mark.parametrize("detail", ["Goal Disallowed - offside", "Goal cancelled"])
def test_var_disallowed_goal_retracts_goal_and_assist(session: Session, detail: str) -> None:
    _seed_catalog(session)
    session.commit()
    fixture = _sync(session, events=_load("fixtures_events.json"))
    assert _bonus(session, fixture, ANTONIO).get("goal") == 3.0

    players = _players_after_disallowed_goal()
    fixture = _sync(session, events=_with_var_disallowed(detail), players=players)
    assert _active_scoring(session, fixture, "goal", ANTONIO) == []
    # Anche la riga della cronologia del gol si ritira (la vista e il conteggio dalla
    # cronologia non lo vedono più); l'evento Var resta.
    timeline_goal = session.scalars(
        select(MatchEvent).where(
            MatchEvent.fixture_id == fixture.id,
            MatchEvent.status == "timeline",
            MatchEvent.event_type == "Goal",
            MatchEvent.athlete_provider_id == ANTONIO,
        )
    ).one()
    assert timeline_goal.is_active is False
    var_row = session.scalars(
        select(MatchEvent)
        .where(MatchEvent.fixture_id == fixture.id, MatchEvent.event_type == "Var")
        .where(MatchEvent.event_detail == detail)
    ).one()
    assert var_row.is_active is True
    assert "goal" not in _bonus(session, fixture, ANTONIO)
    assert _bonus(session, fixture, WARD_PROWSE).get("assist") == 1.0

    # Il VAR sparisce (gol convalidato): tutto torna attivo.
    fixture = _sync(session, events=_load("fixtures_events.json"))
    assert timeline_goal.is_active is True
    assert _bonus(session, fixture, ANTONIO).get("goal") == 3.0
    assert _bonus(session, fixture, WARD_PROWSE).get("assist") == 2.0


def test_empty_events_response_does_not_wipe_scoring_events(session: Session) -> None:
    """Una risposta vuota del fornitore (errore, buco) non cancella i gol della partita."""
    _seed_catalog(session)
    session.commit()
    fixture = _sync(session, events=_load("fixtures_events.json"))
    empty = copy.deepcopy(_load("fixtures_events.json"))
    empty["response"] = []
    empty["results"] = 0
    fixture = _sync(session, events=empty)
    assert len(_active_scoring(session, fixture, "goal", ANTONIO)) == 1
    assert len(_active_scoring(session, fixture, "assist", WARD_PROWSE)) == 2


def test_var_disallowed_on_first_sight_creates_no_bonus(session: Session) -> None:
    _seed_catalog(session)
    session.commit()
    fixture = _sync(
        session, events=_with_var_disallowed(), players=_players_after_disallowed_goal()
    )
    assert _active_scoring(session, fixture, "goal", ANTONIO) == []
    assert "goal" not in _bonus(session, fixture, ANTONIO)
    assert _bonus(session, fixture, WARD_PROWSE).get("assist") == 1.0
