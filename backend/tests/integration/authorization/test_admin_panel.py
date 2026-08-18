"""Authorization tests for the /admin platform panel (EP11-04a)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import LeagueMemberRole, LeagueState, PlatformRole
from database.session import create_session_factory
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from mail.capture import get_captured_emails

ADMIN_PATHS = ["/admin/overview", "/admin/users", "/admin/leagues"]


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
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    user_id = UUID(login.json()["user"]["id"])
    return login.json()["accessToken"], user_id


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


def _promote(db_session: Session, user_id: UUID) -> None:
    user = db_session.get(User, user_id)
    assert user is not None
    user.platform_role = PlatformRole.OPERATOR
    db_session.commit()


def _seed_league(db_session: Session, *, name: str, owner_id: UUID) -> UUID:
    league = League(name=name, season_year=2025, state=LeagueState.DRAFT)
    db_session.add(league)
    db_session.flush()
    db_session.add(
        LeagueMembership(league_id=league.id, user_id=owner_id, role=LeagueMemberRole.OWNER)
    )
    db_session.add(
        LeagueRules(
            league_id=league.id,
            preset_name="standard",
            participant_count=8,
            roster_size=35,
            goalkeepers=3,
            defenders=11,
            midfielders=11,
            forwards=10,
            total_credits=1000,
            allow_trades=True,
            allow_manual_invites=True,
        )
    )
    db_session.commit()
    return league.id


def test_admin_routes_require_authentication(client: TestClient) -> None:
    for path in ADMIN_PATHS:
        response = client.get(path)
        assert response.status_code == 401, path


def test_admin_routes_denied_for_member(client: TestClient, db_session: Session) -> None:
    token, _ = _register_and_login(client, "admin.member@example.com")
    for path in ADMIN_PATHS:
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403, path
        assert response.json()["code"] == "forbidden"


def test_admin_routes_denied_for_league_admin(client: TestClient, db_session: Session) -> None:
    token, user_id = _register_and_login(client, "admin.league.owner@example.com")
    _seed_league(db_session, name="Lega Test", owner_id=user_id)
    for path in ADMIN_PATHS:
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403, path


def test_admin_overview_for_operator(client: TestClient, db_session: Session) -> None:
    token, user_id = _register_and_login(client, "admin.operator.one@example.com")
    _promote(db_session, user_id)

    response = client.get("/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["operatorId"] == str(user_id)
    assert body["environment"] == "test"
    assert body["operatorsCount"] >= 1


def test_admin_users_list_and_promote_revoke(client: TestClient, db_session: Session) -> None:
    op_token, op_id = _register_and_login(client, "admin.operator.two@example.com")
    _promote(db_session, op_id)
    _, target_id = _register_and_login(client, "admin.target@example.com")

    listing = client.get(
        "/admin/users?query=admin.target",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert listing.status_code == 200
    emails = [row["email"] for row in listing.json()["items"]]
    assert "admin.target@example.com" in emails

    promote = client.post(
        f"/admin/users/{target_id}/promote",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert promote.status_code == 200
    assert promote.json()["platformRole"] == "operator"

    revoke = client.post(
        f"/admin/users/{target_id}/revoke",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert revoke.status_code == 200
    assert revoke.json()["platformRole"] == "user"


def test_admin_cannot_revoke_last_operator(client: TestClient, db_session: Session) -> None:
    token, user_id = _register_and_login(client, "admin.sole.operator@example.com")
    _promote(db_session, user_id)
    # Isolate from operators promoted by other tests sharing this module's database.
    db_session.execute(
        update(User)
        .where(User.id != user_id, User.platform_role == PlatformRole.OPERATOR)
        .values(platform_role=PlatformRole.USER)
    )
    db_session.commit()

    response = client.post(
        f"/admin/users/{user_id}/revoke",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "last_operator"


def test_admin_promote_unknown_user_returns_not_found(
    client: TestClient, db_session: Session
) -> None:
    token, user_id = _register_and_login(client, "admin.operator.three@example.com")
    _promote(db_session, user_id)

    missing_id = "00000000-0000-4000-8000-000000000099"
    response = client.post(
        f"/admin/users/{missing_id}/promote",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "admin_user_not_found"


def test_admin_leagues_list_shows_owner(client: TestClient, db_session: Session) -> None:
    token, op_id = _register_and_login(client, "admin.operator.four@example.com")
    _promote(db_session, op_id)
    _, owner_id = _register_and_login(client, "admin.league.owner.two@example.com")
    _seed_league(db_session, name="Lega Globale", owner_id=owner_id)

    response = client.get("/admin/leagues", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    names = {row["name"] for row in response.json()["items"]}
    assert "Lega Globale" in names
