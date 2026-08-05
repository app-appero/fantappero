"""Privacy API integration tests (EP02-04)."""

from __future__ import annotations

import os
import re
from uuid import UUID

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from tests.integration.database.helpers import create_engine_for_url

from auth.models.privacy_audit_event import PrivacyAuditEvent
from auth.models.user import User
from database.enums import LeagueMemberRole, LeagueState, PrivacyAuditAction
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


def _register_and_login(client: TestClient, email: str, display_name: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": display_name},
    )
    token = _extract_token_from_email_body(get_captured_emails()[-1].message.text_body)
    assert token
    client.post("/auth/verify-email", json={"token": token})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    payload = login.json()
    return {
        "access": payload["accessToken"],
        "refresh": payload["refreshToken"],
        "user_id": payload["user"]["id"],
    }


def _seed_league(session: Session, *, owner_id: UUID) -> UUID:
    league = League(name="Lega Privacy", season_year=2025, state=LeagueState.DRAFT)
    session.add(league)
    session.flush()
    session.add(
        LeagueMembership(
            league_id=league.id,
            user_id=owner_id,
            role=LeagueMemberRole.OWNER,
        )
    )
    session.commit()
    return league.id


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


def test_export_returns_readable_payload_and_audit(client: TestClient, db_session: Session) -> None:
    session = _register_and_login(client, "export@example.com", "Giulia Verdi")
    headers = {"Authorization": f"Bearer {session['access']}"}
    _seed_league(db_session, owner_id=UUID(session["user_id"]))

    response = client.get("/profile/me/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers.get("content-disposition", "")

    payload = response.json()
    assert payload["formatVersion"] == "1"
    assert payload["account"]["email"] == "export@example.com"
    assert payload["profile"]["displayName"] == "Giulia Verdi"
    assert len(payload["leagueMemberships"]) == 1
    assert payload["leagueMemberships"][0]["leagueName"] == "Lega Privacy"

    audit = db_session.scalars(
        select(PrivacyAuditEvent).where(
            PrivacyAuditEvent.user_id == UUID(session["user_id"]),
            PrivacyAuditEvent.action == PrivacyAuditAction.DATA_EXPORT,
        )
    ).all()
    assert len(audit) == 1


def test_delete_anonymizes_account_and_preserves_league_history(
    client: TestClient,
    db_session: Session,
) -> None:
    session = _register_and_login(client, "delete@example.com", "Paolo Neri")
    headers = {"Authorization": f"Bearer {session['access']}"}
    _seed_league(db_session, owner_id=UUID(session["user_id"]))

    delete = client.post(
        "/profile/me/delete",
        headers=headers,
        json={"password": "Password123!", "confirmPhrase": "ELIMINA"},
    )
    assert delete.status_code == 200
    assert "eliminato" in delete.json()["message"].lower()

    user = db_session.scalar(
        select(User).options(selectinload(User.profile)).where(User.id == UUID(session["user_id"])),
    )
    assert user is not None
    assert user.deleted_at is not None
    assert user.email.endswith("@anon.fantappero.invalid")
    assert user.profile is not None
    assert user.profile.display_name is None

    membership = db_session.scalar(
        select(LeagueMembership).where(LeagueMembership.user_id == user.id),
    )
    assert membership is not None
    assert membership.historical_display_name == "Paolo Neri"

    login = client.post(
        "/auth/login",
        json={"email": "delete@example.com", "password": "Password123!"},
    )
    assert login.status_code == 401

    refresh = client.post("/auth/refresh", json={"refreshToken": session["refresh"]})
    assert refresh.status_code == 401

    me = client.get("/profile/me", headers=headers)
    assert me.status_code == 401

    audit = db_session.scalars(
        select(PrivacyAuditEvent).where(
            PrivacyAuditEvent.user_id == user.id,
            PrivacyAuditEvent.action == PrivacyAuditAction.ACCOUNT_DELETE,
        )
    ).all()
    assert len(audit) == 1


def test_delete_requires_valid_password_and_confirmation(client: TestClient) -> None:
    session = _register_and_login(client, "guard@example.com", "Guard User")
    headers = {"Authorization": f"Bearer {session['access']}"}

    wrong_password = client.post(
        "/profile/me/delete",
        headers=headers,
        json={"password": "WrongPass123!", "confirmPhrase": "ELIMINA"},
    )
    assert wrong_password.status_code == 401

    wrong_phrase = client.post(
        "/profile/me/delete",
        headers=headers,
        json={"password": "Password123!", "confirmPhrase": "elimina"},
    )
    assert wrong_phrase.status_code == 400
    assert wrong_phrase.json()["code"] == "invalid_delete_confirmation"


def test_privacy_endpoints_require_authentication(client: TestClient) -> None:
    export = client.get("/profile/me/export")
    assert export.status_code == 401

    delete = client.post(
        "/profile/me/delete",
        json={"password": "Password123!", "confirmPhrase": "ELIMINA"},
    )
    assert delete.status_code == 401
