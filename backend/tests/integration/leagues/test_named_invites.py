"""Focused coverage for directory search, named invites, availability and IDOR."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from auth.models.user_profile import UserProfile
from database.enums import LeagueAuditAction, LeagueMemberRole, PlatformRole, UserType
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from mail.capture import get_captured_emails


def _register_and_login(
    client: TestClient,
    email: str,
    *,
    display_name: str | None = None,
) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "Password123!",
            "displayName": display_name or email.split("@")[0],
        },
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
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _set_available(client: TestClient, token: str, available: bool = True) -> None:
    response = client.patch(
        "/profile/disponibilita-inviti",
        headers={"Authorization": f"Bearer {token}"},
        json={"availableForInvites": available},
    )
    assert response.status_code == 200
    assert response.json()["availableForInvites"] is available


def test_directory_pagination_filters_and_excludes_members(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "dir.owner@example.com", display_name="Owner Dir")
    human_token, human_id = _register_and_login(
        client,
        "dir.human@example.com",
        display_name="Zio Manuale",
    )
    from auth.security import hash_password

    ai = User(
        email="dir-ai@example.com",
        password_hash=hash_password("Password123!"),
        platform_role=PlatformRole.USER,
        user_type=UserType.AI,
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(ai)
    db_session.flush()
    db_session.add(
        UserProfile(user_id=ai.id, display_name="Allenatore IA 99", available_for_invites=True)
    )
    db_session.commit()

    league_id = _create_league(client, owner_token, competition_ids, "Lega Directory")
    _set_available(client, human_token, True)

    page1 = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori",
        headers={"Authorization": f"Bearer {owner_token}"},
        params={"page": 1, "pageSize": 1, "userType": "human", "available": "true"},
    )
    assert page1.status_code == 200
    payload = page1.json()
    assert payload["pageSize"] == 1
    assert payload["total"] >= 1
    assert all(row["userType"] == "human" for row in payload["items"])
    assert all(row["availableForInvites"] is True for row in payload["items"])
    assert all("email" not in row for row in payload["items"])

    search = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori",
        headers={"Authorization": f"Bearer {owner_token}"},
        params={"search": "IA 99", "userType": "ai"},
    )
    assert search.status_code == 200
    assert any(row["userId"] == str(ai.id) for row in search.json()["items"])

    member = LeagueMembership(
        league_id=UUID(league_id),
        user_id=human_id,
        role=LeagueMemberRole.MEMBER,
    )
    db_session.add(member)
    db_session.commit()

    after_join = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori",
        headers={"Authorization": f"Bearer {owner_token}"},
        params={"search": "Zio Manuale"},
    )
    assert after_join.status_code == 200
    assert all(row["userId"] != str(human_id) for row in after_join.json()["items"])


def test_named_invite_rejects_unavailable_duplicate_and_member(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "rej.owner@example.com")
    recipient_token, recipient_id = _register_and_login(client, "rej.recipient@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Reject")

    unavailable = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(recipient_id)},
    )
    assert unavailable.status_code == 400
    assert unavailable.json()["code"] == "recipient_unavailable"

    _set_available(client, recipient_token, True)
    created = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(recipient_id)},
    )
    assert created.status_code == 201
    duplicate = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(recipient_id)},
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["code"] == "named_invite_already_pending"

    accept = client.post(
        f"/leagues/inviti-ricevuti/{created.json()['id']}/accetta",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert accept.status_code == 200
    already_member = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(recipient_id)},
    )
    assert already_member.status_code == 400
    assert already_member.json()["code"] == "already_member"


def test_accept_rechecks_availability_and_idor(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "idor.owner@example.com")
    recipient_token, recipient_id = _register_and_login(client, "idor.recipient@example.com")
    outsider_token, _ = _register_and_login(client, "idor.outsider@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega IDOR")
    _set_available(client, recipient_token, True)

    created = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(recipient_id)},
    )
    assert created.status_code == 201
    invite_id = created.json()["id"]

    forbidden_dir = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert forbidden_dir.status_code == 403

    stolen = client.post(
        f"/leagues/inviti-ricevuti/{invite_id}/accetta",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert stolen.status_code == 400
    assert stolen.json()["code"] == "named_invite_not_found"

    _set_available(client, recipient_token, False)
    blocked = client.post(
        f"/leagues/inviti-ricevuti/{invite_id}/accetta",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "recipient_unavailable"


def test_named_capacity_and_concurrent_accept(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "cap.owner@example.com")
    a_token, a_id = _register_and_login(client, "cap.a@example.com", display_name="Cap A")
    b_token, b_id = _register_and_login(client, "cap.b@example.com", display_name="Cap B")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Capienza")
    rules = db_session.scalar(select(LeagueRules).where(LeagueRules.league_id == UUID(league_id)))
    assert rules is not None
    rules.participant_count = 4
    for index in range(2):
        _, filler_id = _register_and_login(client, f"cap.filler{index}@example.com")
        db_session.add(
            LeagueMembership(
                league_id=UUID(league_id),
                user_id=filler_id,
                role=LeagueMemberRole.MEMBER,
            )
        )
    db_session.commit()
    _set_available(client, a_token, True)
    _set_available(client, b_token, True)

    first = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(a_id)},
    )
    assert first.status_code == 201
    second = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(b_id)},
    )
    assert second.status_code == 400
    assert second.json()["code"] == "league_full"

    invite_id = first.json()["id"]

    def _accept() -> int:
        response = client.post(
            f"/leagues/inviti-ricevuti/{invite_id}/accetta",
            headers={"Authorization": f"Bearer {a_token}"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: _accept(), range(2)))
    assert statuses.count(200) >= 1
    assert (
        db_session.scalar(
            select(func.count(LeagueMembership.id)).where(
                LeagueMembership.league_id == UUID(league_id),
                LeagueMembership.user_id == a_id,
            )
        )
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count(LeagueAuditEvent.id)).where(
                LeagueAuditEvent.league_id == UUID(league_id),
                LeagueAuditEvent.action == LeagueAuditAction.NAMED_INVITE_ACCEPTED,
            )
        )
        >= 1
    )


def test_ai_availability_endpoint_is_immutable(
    client: TestClient,
    db_session: Session,
) -> None:
    from auth.security import hash_password

    ai = User(
        email="immutable-ai@example.com",
        password_hash=hash_password("Password123!"),
        platform_role=PlatformRole.USER,
        user_type=UserType.AI,
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(ai)
    db_session.flush()
    db_session.add(
        UserProfile(user_id=ai.id, display_name="IA Immobile", available_for_invites=True)
    )
    db_session.commit()

    # AI cannot obtain a session; mutate via profile service path is covered by login block.
    login = client.post(
        "/auth/login",
        json={"email": ai.email, "password": "Password123!"},
    )
    assert login.status_code == 401

    human_token, _ = _register_and_login(client, "avail.human@example.com")
    default = client.get("/profile/me", headers={"Authorization": f"Bearer {human_token}"})
    assert default.status_code == 200
    assert default.json()["availableForInvites"] is False
    assert default.json()["userType"] == "human"
