"""Integration tests for fantasy teams and roster exclusivity (EP05-01/03)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueAuditAction, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
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
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
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


def _create_league(
    client: TestClient,
    token: str,
    competition_ids: list[str],
    name: str,
) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
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


def test_create_league_creates_owner_fantasy_team_with_empty_slots(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "ft.owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Rosa")

    rosa = client.get(
        f"/leagues/{league_id}/rosa",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rosa.status_code == 200
    body = rosa.json()
    assert body["rosterSize"] == 35
    assert body["filledSlots"] == 0
    assert body["compositionStatus"] == "incomplete"
    assert body["composition"]["counts"] == {"P": 0, "D": 0, "C": 0, "A": 0}
    assert len(body["slots"]) == 35
    assert all(slot["athleteId"] is None for slot in body["slots"])

    teams = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).all()
    assert len(teams) == 1
    slot_count = db_session.scalar(
        select(func.count(FantasyRosterSlot.id)).where(
            FantasyRosterSlot.fantasy_team_id == teams[0].id
        )
    )
    assert slot_count == 35


def test_ensure_teams_idempotent_and_get_rosa_permissions(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "ft.ensure.owner@example.com")
    member_token, member_id = _register_and_login(client, "ft.ensure.member@example.com")
    outsider_token, _ = _register_and_login(client, "ft.ensure.out@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Ensure")
    _add_member(db_session, league_id, member_id)

    first = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert first.status_code == 200
    assert first.json()["created"] >= 1
    assert first.json()["existing"] >= 1

    second = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert second.status_code == 200
    assert second.json()["created"] == 0
    assert second.json()["existing"] == 2

    member_rosa = client.get(
        f"/leagues/{league_id}/rosa",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert member_rosa.status_code == 200
    assert member_rosa.json()["userId"] == str(member_id)

    forbidden = client.get(
        f"/leagues/{league_id}/rosa",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert forbidden.status_code == 403


def test_assign_rejects_double_ownership_same_league(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "ft.excl.owner@example.com")
    _, member_id = _register_and_login(client, "ft.excl.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Exclusivity")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, provider_id=900001, name="Calciatore Unico")

    ensured = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert ensured.status_code == 200
    teams = ensured.json()["teams"]
    assert len(teams) == 2
    team_a = teams[0]["id"]
    team_b = teams[1]["id"]

    assigned = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_a}/slot/0",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 1},
    )
    assert assigned.status_code == 200
    assert assigned.json()["filledSlots"] == 1

    conflict = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_b}/slot/0",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 1},
    )
    assert conflict.status_code == 400
    assert conflict.json()["code"] == "athlete_already_owned"

    owned = db_session.scalar(
        select(func.count(FantasyRosterSlot.id)).where(
            FantasyRosterSlot.league_id == UUID(league_id),
            FantasyRosterSlot.athlete_id == athlete.id,
        )
    )
    assert owned == 1

    audit_count = db_session.scalar(
        select(func.count(LeagueAuditEvent.id)).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROSTER_SLOT_ASSIGNED,
        )
    )
    assert audit_count == 1


def test_concurrent_assign_same_athlete_no_double_ownership(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "ft.conc.owner@example.com")
    _, member_id = _register_and_login(client, "ft.conc.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Concurrent")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, provider_id=900002, name="Calciatore Race")

    ensured = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert ensured.status_code == 200
    team_a = ensured.json()["teams"][0]["id"]
    team_b = ensured.json()["teams"][1]["id"]

    def _assign(team_id: str) -> int:
        response = client.put(
            f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/1",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"athleteId": str(athlete.id), "purchaseCredits": 1},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(_assign, [team_a, team_b]))

    assert statuses.count(200) == 1
    assert statuses.count(400) == 1
    owned = db_session.scalar(
        select(func.count(FantasyRosterSlot.id)).where(
            FantasyRosterSlot.league_id == UUID(league_id),
            FantasyRosterSlot.athlete_id == athlete.id,
        )
    )
    assert owned == 1


def test_release_slot_idempotent(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "ft.rel.owner@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Release")
    athlete = _seed_athlete(db_session, provider_id=900003, name="Calciatore Liberabile")
    rosa = client.get(
        f"/leagues/{league_id}/rosa",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    team_id = rosa.json()["id"]

    assigned = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/2",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 1},
    )
    assert assigned.status_code == 200

    released = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/2",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert released.status_code == 200
    assert released.json()["filledSlots"] == 0

    again = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/2",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert again.status_code == 200

    missing = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/2",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"athleteId": str(uuid4()), "purchaseCredits": 1},
    )
    assert missing.status_code == 400
    assert missing.json()["code"] == "athlete_not_found"


def test_admin_get_team_detail_and_member_forbidden(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "ft.admin.detail@example.com")
    member_token, member_id = _register_and_login(client, "ft.member.detail@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Admin Detail")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, provider_id=900004, name="Calciatore Admin View")

    ensured = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert ensured.status_code == 200
    team_id = ensured.json()["teams"][0]["id"]

    assigned = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 1},
    )
    assert assigned.status_code == 200

    detail = client.get(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == team_id
    assert body["filledSlots"] == 1
    assert body["slots"][0]["athleteId"] == str(athlete.id)
    assert body["slots"][0]["athleteName"] == "Calciatore Admin View"

    forbidden = client.get(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert forbidden.status_code == 403


def test_member_can_edit_own_roster_not_others_and_purchase_is_tracked(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "ft.self.owner@example.com")
    member_token, member_id = _register_and_login(client, "ft.self.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Self Edit")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, provider_id=900005, name="Calciatore Self")

    ensured = client.post(
        f"/leagues/{league_id}/amministrazione/squadre",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert ensured.status_code == 200

    member_rosa = client.get(
        f"/leagues/{league_id}/rosa",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert member_rosa.status_code == 200
    member_team = member_rosa.json()["id"]
    owner_rosa = client.get(
        f"/leagues/{league_id}/rosa",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    owner_team_id = owner_rosa.json()["id"]

    credits_before = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert credits_before.status_code == 200
    balance_before = credits_before.json()["balance"]

    assigned = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{member_team}/slot/0",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 15},
    )
    assert assigned.status_code == 200
    assert assigned.json()["slots"][0]["purchaseCredits"] == 15
    assert assigned.json()["slots"][0]["athleteName"] == "Calciatore Self"

    credits_after = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert credits_after.json()["balance"] == balance_before - 15

    forbidden = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{owner_team_id}/slot/1",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 1},
    )
    assert forbidden.status_code == 400
    assert forbidden.json()["code"] == "roster_edit_forbidden"

    occupancy = client.get(
        f"/leagues/{league_id}/occupazione-rosa",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert occupancy.status_code == 200
    assert any(row["athleteId"] == str(athlete.id) for row in occupancy.json())

    peer_roster = client.get(
        f"/leagues/{league_id}/squadre/{member_team}/giocatori",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert peer_roster.status_code == 200
    assert any(row["athleteId"] == str(athlete.id) for row in peer_roster.json())
    assert peer_roster.json()[0]["athleteName"]

    released = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{member_team}/slot/0",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert released.status_code == 200
    credits_refunded = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert credits_refunded.json()["balance"] == balance_before


def test_assign_rejects_role_quota_exceeded(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "ft.quota@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Quote")
    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    team_id = rosa.json()["id"]

    keepers = [
        _seed_athlete(db_session, 901000 + index, f"Portiere {index}", role=FantasyRole.P)
        for index in range(4)
    ]
    for index, athlete in enumerate(keepers[:3]):
        response = client.put(
            f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{index}",
            headers={"Authorization": f"Bearer {token}"},
            json={"athleteId": str(athlete.id), "purchaseCredits": 1},
        )
        assert response.status_code == 200, response.json()

    overflow = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/3",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(keepers[3].id), "purchaseCredits": 1},
    )
    assert overflow.status_code == 400
    assert overflow.json()["code"] == "role_quota_exceeded"

    body = client.get(
        f"/leagues/{league_id}/rosa",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert body["compositionStatus"] == "incomplete"
    assert body["composition"]["counts"]["P"] == 3
    assert body["filledSlots"] == 3
