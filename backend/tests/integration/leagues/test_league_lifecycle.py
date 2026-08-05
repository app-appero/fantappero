"""Integration coverage for EP03-05 league lifecycle."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueAuditAction, LeagueMemberRole, LeagueState
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails


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


def _transition(client: TestClient, token: str, league_id: str, target: str):
    return client.post(
        f"/leagues/{league_id}/amministrazione/stato",
        headers={"Authorization": f"Bearer {token}"},
        json={"targetState": target},
    )


def _standard_rules_payload(participant_count: int) -> dict[str, object]:
    return {
        "presetName": "standard",
        "participantCount": participant_count,
        "roster": {
            "rosterSize": 35,
            "goalkeepers": 3,
            "defenders": 11,
            "midfielders": 11,
            "forwards": 10,
        },
        "totalCredits": 1000,
        "options": {"allowTrades": True, "allowManualInvites": True},
    }


def test_draft_to_auction_is_audited_idempotent_and_active_stays_blocked(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "lifecycle.owner@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Lifecycle")

    panel = client.get(
        f"/leagues/{league_id}/amministrazione",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert panel.status_code == 200
    assert panel.json()["lifecycle"] == {
        "state": "draft",
        "allowedTransitions": ["configuring"],
        "blockers": [],
    }

    configuring = _transition(client, owner_token, league_id, "configuring")
    assert configuring.status_code == 200
    assert configuring.json()["state"] == "configuring"
    assert configuring.json()["allowedTransitions"] == []
    assert {row["code"] for row in configuring.json()["blockers"]} == {"participant_count_mismatch"}

    rules_update = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=_standard_rules_payload(4),
    )
    assert rules_update.status_code == 200
    assert rules_update.json()["participantCount"] == 4
    invite = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"expiresInDays": 7},
    )
    assert invite.status_code == 201
    for index in range(3):
        member_token, _ = _register_and_login(
            client,
            f"lifecycle.member{index}@example.com",
        )
        accepted = client.post(
            "/leagues/inviti/accetta",
            headers={"Authorization": f"Bearer {member_token}"},
            json={"token": invite.json()["token"]},
        )
        assert accepted.status_code == 200
        assert accepted.json()["alreadyMember"] is False

    auction = _transition(client, owner_token, league_id, "auction")
    assert auction.status_code == 200
    assert auction.json()["state"] == "auction"
    assert auction.json()["allowedTransitions"] == ["configuring"]
    assert {row["code"] for row in auction.json()["blockers"]} == {
        "calendar_not_configured",
        "fantasy_teams_not_configured",
        "credits_not_configured",
    }

    noop = _transition(client, owner_token, league_id, "auction")
    blocked = _transition(client, owner_token, league_id, "active")
    assert noop.status_code == 200
    assert noop.json()["state"] == "auction"
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "league_transition_blocked"

    db_session.expire_all()
    league = db_session.get(League, UUID(league_id))
    assert league is not None
    assert league.state == LeagueState.AUCTION
    audits = db_session.scalars(
        select(LeagueAuditEvent)
        .where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_STATE_CHANGED,
        )
        .order_by(LeagueAuditEvent.created_at.asc())
    ).all()
    assert len(audits) == 2
    assert [audit.details for audit in audits] == [
        {"before": "draft", "after": "configuring"},
        {"before": "configuring", "after": "auction"},
    ]
    assert all(audit.actor_id == owner_id for audit in audits)


def test_invalid_transition_is_rejected(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lifecycle.invalid@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Salto")

    response = _transition(client, token, league_id, "auction")

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_league_transition"


def test_transition_requires_league_admin(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "lifecycle.permission.owner@example.com")
    member_token, member_id = _register_and_login(
        client,
        "lifecycle.permission.member@example.com",
    )
    league_id = _create_league(client, owner_token, competition_ids, "Lega Permesso Stato")
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id),
            user_id=member_id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    db_session.commit()

    response = _transition(client, member_token, league_id, "configuring")

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"
    assert (
        db_session.scalar(
            select(func.count(LeagueAuditEvent.id)).where(
                LeagueAuditEvent.league_id == UUID(league_id),
                LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_STATE_CHANGED,
            )
        )
        == 0
    )
