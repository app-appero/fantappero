"""Privacy isolation — export/delete only for the authenticated owner (EP02-04)."""

from __future__ import annotations

import os
import re
from uuid import UUID

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueMemberRole, LeagueState
from database.session import create_session_factory
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails


@pytest.fixture(autouse=True)
def _clear_auth_rate_limits() -> None:
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    for key in client.scan_iter("auth:rl:*"):
        client.delete(key)


def _extract_token_from_email_body(body: str) -> str | None:
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    return match.group(1) if match else None


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    token = _extract_token_from_email_body(get_captured_emails()[-1].message.text_body)
    assert token
    client.post("/auth/verify-email", json={"token": token})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    user_id = UUID(login.json()["user"]["id"])
    return login.json()["accessToken"], user_id


def _seed_cross_league_membership(
    session: Session,
    *,
    owner_id: UUID,
    member_id: UUID,
) -> None:
    league = League(name="Lega condivisa", season_year=2025, state=LeagueState.DRAFT)
    session.add(league)
    session.flush()
    session.add(
        LeagueMembership(
            league_id=league.id,
            user_id=owner_id,
            role=LeagueMemberRole.OWNER,
        )
    )
    session.add(
        LeagueMembership(
            league_id=league.id,
            user_id=member_id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    session.commit()


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_delete_only_affects_authenticated_user(client: TestClient) -> None:
    token_a, _ = _register_and_login(client, "privacy.a@example.com")
    token_b, _ = _register_and_login(client, "privacy.b@example.com")

    delete_b = client.post(
        "/profile/me/delete",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"password": "Password123!", "confirmPhrase": "ELIMINA"},
    )
    assert delete_b.status_code == 200

    still_there = client.get("/profile/me/export", headers={"Authorization": f"Bearer {token_a}"})
    assert still_there.status_code == 200
    assert still_there.json()["account"]["email"] == "privacy.a@example.com"

    blocked_b = client.get("/profile/me/export", headers={"Authorization": f"Bearer {token_b}"})
    assert blocked_b.status_code == 401


def test_deleting_member_preserves_shared_league_for_owner(
    client: TestClient,
    db_session: Session,
) -> None:
    owner_token, owner_id = _register_and_login(client, "owner.privacy@example.com")
    member_token, member_id = _register_and_login(client, "member.privacy@example.com")
    _seed_cross_league_membership(db_session, owner_id=owner_id, member_id=member_id)

    delete_member = client.post(
        "/profile/me/delete",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"password": "Password123!", "confirmPhrase": "ELIMINA"},
    )
    assert delete_member.status_code == 200

    owner_export = client.get(
        "/profile/me/export",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_export.status_code == 200
    memberships = owner_export.json()["leagueMemberships"]
    assert len(memberships) == 1
    assert memberships[0]["leagueName"] == "Lega condivisa"
    assert memberships[0]["historicalDisplayName"] is None

    member_membership = db_session.scalar(
        select(LeagueMembership).where(LeagueMembership.user_id == member_id),
    )
    assert member_membership is not None
    assert member_membership.historical_display_name == "member.privacy"
