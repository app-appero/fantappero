"""Integration coverage for EP03-06 H2H calendar."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueAuditAction, LeagueCalendarStatus
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import LeagueCalendar
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


def _create_league_with_members(
    client: TestClient,
    competition_ids: list[str],
    *,
    size: int,
    prefix: str,
) -> tuple[str, str, list[str]]:
    owner_token, _ = _register_and_login(client, f"{prefix}.owner@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": f"Lega Calendario {prefix}",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert created.status_code == 201
    league_id = created.json()["id"]

    rules = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {owner_token}"},
        json=_standard_rules_payload(size),
    )
    assert rules.status_code == 200

    invite = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"expiresInDays": 7},
    )
    assert invite.status_code == 201
    member_tokens: list[str] = []
    for index in range(size - 1):
        token, _ = _register_and_login(client, f"{prefix}.member{index}@example.com")
        accepted = client.post(
            "/leagues/inviti/accetta",
            headers={"Authorization": f"Bearer {token}"},
            json={"token": invite.json()["token"]},
        )
        assert accepted.status_code == 200
        member_tokens.append(token)

    configuring = client.post(
        f"/leagues/{league_id}/amministrazione/stato",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"targetState": "configuring"},
    )
    assert configuring.status_code == 200
    return league_id, owner_token, member_tokens


def test_generate_confirm_calendar_is_audited_and_clears_blocker(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    league_id, owner_token, member_tokens = _create_league_with_members(
        client,
        competition_ids,
        size=4,
        prefix="cal.ok",
    )

    empty = client.get(
        f"/leagues/{league_id}/amministrazione/calendario",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert empty.status_code == 200
    assert empty.json() is None

    forbidden = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {member_tokens[0]}"},
    )
    assert forbidden.status_code == 403

    generated = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["status"] == "draft"
    assert body["format"] == "single_round_robin"
    assert body["participantCount"] == 4
    assert body["roundCount"] == 3
    assert body["matchupCount"] == 6
    assert body["byeCount"] == 0
    assert len(body["rounds"]) == 3

    public_before = client.get(
        f"/leagues/{league_id}/calendario",
        headers={"Authorization": f"Bearer {member_tokens[0]}"},
    )
    assert public_before.status_code == 200
    assert public_before.json() is None

    confirmed = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/conferma",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"

    noop = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/conferma",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert noop.status_code == 200
    assert noop.json()["status"] == "confirmed"

    public_after = client.get(
        f"/leagues/{league_id}/calendario",
        headers={"Authorization": f"Bearer {member_tokens[0]}"},
    )
    assert public_after.status_code == 200
    assert public_after.json()["status"] == "confirmed"

    auction = client.post(
        f"/leagues/{league_id}/amministrazione/stato",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"targetState": "auction"},
    )
    assert auction.status_code == 200
    assert "calendar_not_configured" not in {
        row["code"] for row in auction.json()["blockers"]
    }
    assert {row["code"] for row in auction.json()["blockers"]} == {
        "fantasy_teams_not_configured",
        "credits_not_configured",
    }

    db_session.expire_all()
    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == UUID(league_id))
    ).first()
    assert calendar is not None
    assert calendar.status == LeagueCalendarStatus.CONFIRMED
    audits = db_session.scalars(
        select(LeagueAuditEvent)
        .where(LeagueAuditEvent.league_id == UUID(league_id))
        .order_by(LeagueAuditEvent.created_at.asc())
    ).all()
    actions = [audit.action for audit in audits]
    assert LeagueAuditAction.LEAGUE_CALENDAR_GENERATED in actions
    assert LeagueAuditAction.LEAGUE_CALENDAR_CONFIRMED in actions
    assert actions.count(LeagueAuditAction.LEAGUE_CALENDAR_CONFIRMED) == 1


def test_calendar_generation_requires_exact_participant_count(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "cal.mismatch.owner@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "name": "Lega Calendario Mismatch",
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert created.status_code == 201
    league_id = created.json()["id"]
    assert (
        client.post(
            f"/leagues/{league_id}/amministrazione/stato",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"targetState": "configuring"},
        ).status_code
        == 200
    )

    response = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "participant_count_mismatch"


def test_odd_participant_calendar_uses_explicit_byes(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    league_id, owner_token, _ = _create_league_with_members(
        client,
        competition_ids,
        size=5,
        prefix="cal.odd",
    )
    generated = client.post(
        f"/leagues/{league_id}/amministrazione/calendario/genera",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert generated.status_code == 200
    body = generated.json()
    assert body["participantCount"] == 5
    assert body["roundCount"] == 5
    assert body["matchupCount"] == 10
    assert body["byeCount"] == 5
    bye_rounds = [
        matchup
        for round_row in body["rounds"]
        for matchup in round_row["matchups"]
        if matchup["isBye"]
    ]
    assert len(bye_rounds) == 5
    assert all(matchup["awayUserId"] is None for matchup in bye_rounds)
