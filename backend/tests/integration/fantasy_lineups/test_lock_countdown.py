"""Integration tests for GET /leagues/{league_id}/formazione/prossimo-blocco (EP-turni-automazione)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyTurnKind, FantasyTurnStatus
from database.session import create_session_factory
from fantasy_turns.models import FantasyRound
from leagues.models.competition import Competition
from leagues.models.league_rules import LeagueRules
from tests.integration.fantasy_lineups.test_fantasy_lineups import (
    _create_league,
    _create_open_round,
    _fill_validated_roster,
    _register_and_login,
    _seed_roster_athletes,
    _set_athlete_club,
)

_ENDPOINT = "prossimo-blocco"


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    assert len(rows) >= 3
    return [str(row.id) for row in rows[:3]]


def _countdown(client: TestClient, token: str, league_id: str) -> dict:
    response = client.get(
        f"/leagues/{league_id}/formazione/{_ENDPOINT}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_no_active_turn_when_the_league_has_no_rounds(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "countdown.empty@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Countdown Vuota")

    body = _countdown(client, token, league_id)
    assert body["state"] == "no_active_turn"
    assert body["nextLockAt"] is None
    assert body["roundId"] is None


def test_turn_not_open_when_the_reference_round_is_scheduled(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "countdown.scheduled@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Countdown Scheduled")

    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now + timedelta(days=1),
        window_end_at=now + timedelta(days=4),
        status=FantasyTurnStatus.SCHEDULED,
        generated_at=now,
    )
    db_session.add(fantasy_round)
    db_session.commit()

    body = _countdown(client, token, league_id)
    assert body["state"] == "turn_not_open"
    assert body["nextLockAt"] is None
    assert body["roundNumber"] == 1


def test_no_roster_when_the_team_has_no_players_assigned(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "countdown.noroster@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Countdown Senza Rosa")
    # Materializza la squadra (lazy) senza mai assegnarle giocatori — caso
    # reale di una lega pre-asta con turno già aperto.
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=1),
        id_offset=4_400_000,
        competition_ids=competition_ids,
    )

    body = _countdown(client, token, league_id)
    assert body["state"] == "no_roster"
    assert body["nextLockAt"] is None
    assert body["roundId"] == str(fantasy_round.id)


def test_no_pending_lock_when_every_owned_player_is_already_locked(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "countdown.alllocked@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Countdown Tutti Bloccati")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=4_500_000)
    _fill_validated_roster(db_session, league_id, grouped)

    past_kickoff = datetime.now(UTC) - timedelta(minutes=10)
    fantasy_round, clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=past_kickoff,
        id_offset=4_510_000,
        competition_ids=competition_ids,
    )
    # Tutti gli atleti della rosa giocano nell'unico club già iniziato.
    for role_athletes in grouped.values():
        for athlete in role_athletes:
            _set_athlete_club(db_session, athlete, clubs[0])

    body = _countdown(client, token, league_id)
    assert body["state"] == "no_pending_lock"
    assert body["nextLockAt"] is None
    assert body["roundId"] == str(fantasy_round.id)


def test_counting_down_picks_the_earliest_unlocked_kickoff_with_league_margin(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "countdown.ticking@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Countdown Attivo")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=4_600_000)
    _fill_validated_roster(db_session, league_id, grouped)

    rules = db_session.scalars(
        select(LeagueRules).where(LeagueRules.league_id == UUID(league_id))
    ).one()
    rules.lineup_lock_margin_minutes = 20
    db_session.commit()

    soon_kickoff = datetime.now(UTC) + timedelta(minutes=10)  # dentro il margine: già bloccato
    later_kickoff = datetime.now(UTC) + timedelta(hours=3)  # fuori margine: ancora libero
    fantasy_round, clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=soon_kickoff,
        extra_kickoff=later_kickoff,
        id_offset=4_610_000,
        competition_ids=competition_ids,
    )
    goalkeeper = grouped["P"][0]
    midfielder = grouped["C"][0]
    _set_athlete_club(db_session, goalkeeper, clubs[0])  # soon_kickoff, club 0-1
    _set_athlete_club(db_session, midfielder, clubs[2])  # later_kickoff, club 2-3

    body = _countdown(client, token, league_id)
    assert body["state"] == "counting_down"
    assert body["roundId"] == str(fantasy_round.id)
    next_lock_at = datetime.fromisoformat(body["nextLockAt"].replace("Z", "+00:00"))
    assert next_lock_at == later_kickoff


def test_turn_not_open_never_creates_a_team(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """L'endpoint non deve materializzare una FantasyTeam per un membro che
    non ce l'ha ancora, se il turno di riferimento non è ancora aperto —
    nessuna formazione è schierabile, quindi non serve scrivere dati solo
    per un widget di sola lettura chiamato da ogni pagina.

    Il proprietario ottiene già la sua squadra alla creazione della lega
    (`leagues/service.py`) — per verificare davvero l'assenza di scrittura
    lato countdown serve un secondo membro la cui squadra non è ancora stata
    materializzata da nient'altro.
    """
    from database.enums import LeagueMemberRole
    from fantasy_teams.models import FantasyTeam
    from leagues.models.league_membership import LeagueMembership

    owner_token, _ = _register_and_login(client, "countdown.lazyturn.owner@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Countdown Turno Chiuso")
    member_token, member_id = _register_and_login(
        client, "countdown.lazyturn.member@example.com"
    )
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id), user_id=member_id, role=LeagueMemberRole.MEMBER
        )
    )
    db_session.commit()

    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now + timedelta(days=1),
        window_end_at=now + timedelta(days=4),
        status=FantasyTurnStatus.SCHEDULED,
        generated_at=now,
    )
    db_session.add(fantasy_round)
    db_session.commit()

    before = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).all()
    assert len(before) == 1  # solo quella del proprietario

    body = _countdown(client, member_token, league_id)
    assert body["state"] == "turn_not_open"

    after = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).all()
    assert len(after) == 1  # invariato: il membro non ha ricevuto una squadra
