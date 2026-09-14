"""Integration tests for the EP08-09 follow-up nomination modes.

Covers ``turn_based`` (fixed team rotation drawn at creation) and the two
server-generated queues, ``alphabetical_by_role`` and ``random`` — all three
additive to the original ``manual``/``sequential`` pair.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import FantasyTeam
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


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


def _create_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_member(db_session: Session, league_id: str, user_id: UUID) -> LeagueMembership:
    membership = LeagueMembership(
        league_id=UUID(league_id),
        user_id=user_id,
        role=LeagueMemberRole.MEMBER,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    return membership


def _seed_athlete(
    db_session: Session,
    provider_id: int,
    name: str,
    *,
    role: FantasyRole = FantasyRole.A,
    season_year: int = 2026,
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=season_year,
            role=role,
            mapping_version="v1.0.0",
            provider_position_raw=role.value,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _session_payload(*, nomination_mode: str, **overrides: object) -> dict:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "opensAt": now.isoformat(),
        "closesAt": (now + timedelta(hours=2)).isoformat(),
        "nominationMode": nomination_mode,
        "minIncrementCredits": 10,
        "softCloseSeconds": 5,
        "lotDurationSeconds": 30,
    }
    payload.update(overrides)
    return payload


def _team_owner_user_id(db_session: Session, fantasy_team_id: UUID) -> UUID:
    team = db_session.get(FantasyTeam, fantasy_team_id)
    assert team is not None
    membership = db_session.get(LeagueMembership, team.membership_id)
    assert membership is not None
    return membership.user_id


def _start(client: TestClient, admin_token: str, league_id: str, session_id: str) -> None:
    started = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/avvia",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert started.status_code == 200


def _pass(
    client: TestClient, admin_token: str, league_id: str, session_id: str, lot_id: str
) -> None:
    passed = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/salta",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert passed.status_code == 200


# -- alphabetical_by_role -----------------------------------------------------


def test_alphabetical_by_role_orders_queue_and_excludes_occupied(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.nom.alpha.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Alfabetico")

    keeper = _seed_athlete(db_session, 94001, "Zeta Portiere", role=FantasyRole.P)
    defender = _seed_athlete(db_session, 94002, "Alfa Difensore", role=FantasyRole.D)
    occupied_forward = _seed_athlete(db_session, 94003, "Beta Attaccante", role=FantasyRole.A)

    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert rosa.status_code == 200
    team_id = rosa.json()["id"]
    assign = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"athleteId": str(occupied_forward.id), "purchaseCredits": 1},
    )
    assert assign.status_code == 200, assign.json()

    created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_session_payload(nomination_mode="alphabetical_by_role"),
    )
    assert created.status_code == 201, created.json()
    assert created.json()["queueRemaining"] == 2
    session_id = created.json()["id"]
    _start(client, admin_token, league_id, session_id)

    first_lot = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert first_lot.status_code == 201, first_lot.json()
    # P sorts before D regardless of name ("Zeta" would lose alphabetically).
    assert first_lot.json()["athleteId"] == str(keeper.id)
    _pass(client, admin_token, league_id, session_id, first_lot.json()["id"])

    second_lot = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert second_lot.status_code == 201
    assert second_lot.json()["athleteId"] == str(defender.id)


# -- random --------------------------------------------------------------------


def test_random_mode_generates_full_queue_and_empties_it(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.nom.random.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Casuale")
    athletes = [
        _seed_athlete(db_session, 94100 + i, f"Calciatore Casuale {i}", role=FantasyRole.A)
        for i in range(5)
    ]

    created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_session_payload(nomination_mode="random"),
    )
    assert created.status_code == 201
    assert created.json()["queueRemaining"] == 5
    session_id = created.json()["id"]
    _start(client, admin_token, league_id, session_id)

    nominated_ids: set[str] = set()
    for _ in range(5):
        lot = client.post(
            f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={},
        )
        assert lot.status_code == 201, lot.json()
        nominated_ids.add(lot.json()["athleteId"])
        _pass(client, admin_token, league_id, session_id, lot.json()["id"])

    assert nominated_ids == {str(athlete.id) for athlete in athletes}

    exhausted = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={},
    )
    assert exhausted.status_code == 400
    assert exhausted.json()["code"] == "market_live_queue_empty"


# -- turn_based ------------------------------------------------------------------


def test_turn_based_rotation_is_drawn_once_and_covers_every_member(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, admin_id = _register_and_login(client, "live.nom.turn.admin@example.com")
    member_a_token, member_a_id = _register_and_login(client, "live.nom.turn.a@example.com")
    member_b_token, member_b_id = _register_and_login(client, "live.nom.turn.b@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega A Turno")
    _add_member(db_session, league_id, member_a_id)
    _add_member(db_session, league_id, member_b_id)

    created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_session_payload(nomination_mode="turn_based"),
    )
    assert created.status_code == 201, created.json()
    turn_order = created.json()["turnOrder"]
    assert sorted(entry["position"] for entry in turn_order) == [0, 1, 2]
    owner_ids = {
        _team_owner_user_id(db_session, UUID(entry["fantasyTeamId"])) for entry in turn_order
    }
    assert owner_ids == {admin_id, member_a_id, member_b_id}

    # Drawn once: refetching the session returns the exact same rotation.
    refetched = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{created.json()['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sorted(refetched.json()["turnOrder"], key=lambda e: e["position"]) == sorted(
        turn_order, key=lambda e: e["position"]
    )


def test_turn_based_wrong_member_rejected_own_turn_and_admin_always_allowed(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, admin_id = _register_and_login(client, "live.nom.turn.auth.admin@example.com")
    member_a_token, member_a_id = _register_and_login(client, "live.nom.turn.auth.a@example.com")
    member_b_token, member_b_id = _register_and_login(client, "live.nom.turn.auth.b@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Turno Permessi")
    _add_member(db_session, league_id, member_a_id)
    _add_member(db_session, league_id, member_b_id)
    tokens_by_user_id = {
        admin_id: admin_token,
        member_a_id: member_a_token,
        member_b_id: member_b_token,
    }
    athletes = [
        _seed_athlete(db_session, 94300 + i, f"Permessi {i}", role=FantasyRole.A) for i in range(2)
    ]

    created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_session_payload(nomination_mode="turn_based"),
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    turn_order = sorted(created.json()["turnOrder"], key=lambda e: e["position"])
    assert len(turn_order) == 3
    first_owner = _team_owner_user_id(db_session, UUID(turn_order[0]["fantasyTeamId"]))
    second_owner = _team_owner_user_id(db_session, UUID(turn_order[1]["fantasyTeamId"]))
    _start(client, admin_token, league_id, session_id)

    # Round 1 (team at position 0's turn): an unrelated, non-admin member is
    # rejected; the rightful team succeeds.
    wrong_owner = next(uid for uid in tokens_by_user_id if uid not in (first_owner, admin_id))
    wrong_turn = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {tokens_by_user_id[wrong_owner]}"},
        json={"athleteId": str(athletes[0].id)},
    )
    assert wrong_turn.status_code == 400
    assert wrong_turn.json()["code"] == "market_live_not_your_turn"

    own_turn = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {tokens_by_user_id[first_owner]}"},
        json={"athleteId": str(athletes[0].id)},
    )
    assert own_turn.status_code == 201, own_turn.json()
    _pass(client, admin_token, league_id, session_id, own_turn.json()["id"])

    # Round 2 (team at position 1's turn): same rejection, plus the admin may
    # call on anyone's behalf regardless of whose turn it actually is.
    wrong_owner_2 = next(uid for uid in tokens_by_user_id if uid not in (second_owner, admin_id))
    wrong_turn_2 = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {tokens_by_user_id[wrong_owner_2]}"},
        json={"athleteId": str(athletes[1].id)},
    )
    assert wrong_turn_2.status_code == 400
    assert wrong_turn_2.json()["code"] == "market_live_not_your_turn"

    admin_on_behalf = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"athleteId": str(athletes[1].id)},
    )
    assert admin_on_behalf.status_code == 201, admin_on_behalf.json()


def test_state_reports_current_turn_team_and_advances_after_lot_closes(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, admin_id = _register_and_login(client, "live.nom.turn.state.admin@example.com")
    member_token, member_id = _register_and_login(client, "live.nom.turn.state.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Turno Stato")
    _add_member(db_session, league_id, member_id)
    athlete_a = _seed_athlete(db_session, 94400, "Stato Uno", role=FantasyRole.A)

    created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_session_payload(nomination_mode="turn_based"),
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    turn_order = sorted(created.json()["turnOrder"], key=lambda e: e["position"])
    first_team_id = turn_order[0]["fantasyTeamId"]
    first_team_name = turn_order[0]["fantasyTeamName"]
    second_team_id = turn_order[1]["fantasyTeamId"]
    _start(client, admin_token, league_id, session_id)

    state_before = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert state_before.status_code == 200
    assert state_before.json()["currentTurnTeamId"] == first_team_id
    assert state_before.json()["currentTurnTeamName"] == first_team_name

    lot = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"athleteId": str(athlete_a.id)},
    )
    assert lot.status_code == 201
    _pass(client, admin_token, league_id, session_id, lot.json()["id"])

    state_after = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert state_after.status_code == 200
    assert state_after.json()["currentTurnTeamId"] == second_team_id


# -- shared validation across all three new modes --------------------------------


def test_new_modes_reject_admin_supplied_nomination_queue(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.nom.noqueue.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Coda Non Ammessa")
    athlete = _seed_athlete(db_session, 94500, "Coda Non Ammessa")

    for mode in ("turn_based", "alphabetical_by_role", "random"):
        response = client.post(
            f"/leagues/{league_id}/mercato/asta-live/sessioni",
            headers={"Authorization": f"Bearer {admin_token}"},
            json=_session_payload(
                nomination_mode=mode, nominationQueueAthleteIds=[str(athlete.id)]
            ),
        )
        assert response.status_code == 400, (mode, response.json())
        assert response.json()["code"] == "nomination_queue_not_allowed"
