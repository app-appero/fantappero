"""Auth integration flows (EP02-01)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from tests.integration.auth.conftest import auth_header

from auth.tokens import generate_opaque_token, hash_token
from database.enums import AuthTokenType, LeagueMemberRole, LeagueState
from database.models.accounts import AuthToken
from database.models.competitions import Competition
from database.models.leagues import League, LeagueMembership


def _register(client, email: str, password: str = "Secret123") -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def test_register_login_me_logout_flow(client) -> None:
    payload = _register(client, "player@example.com")
    token = payload["access_token"]

    me = client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["email"] == "player@example.com"
    assert me.json()["email_verified"] is False

    logout = client.post("/auth/logout", headers=auth_header(token))
    assert logout.status_code == 200

    after_logout = client.get("/auth/me", headers=auth_header(token))
    assert after_logout.status_code == 401
    assert after_logout.json()["code"] == "invalid_session"


def test_login_invalid_credentials(client) -> None:
    _register(client, "known@example.com")
    response = client.post(
        "/auth/login",
        json={"email": "known@example.com", "password": "WrongPass1"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_register_duplicate_email(client) -> None:
    _register(client, "dup@example.com")
    response = client.post(
        "/auth/register",
        json={"email": "dup@example.com", "password": "Secret123"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"


def test_verify_email_and_password_reset(client, db) -> None:
    payload = _register(client, "verify@example.com")
    user_id = client.get("/auth/me", headers=auth_header(payload["access_token"])).json()["id"]

    raw_verify = generate_opaque_token()
    db.add(
        AuthToken(
            user_id=user_id,
            token_hash=hash_token(raw_verify),
            token_type=AuthTokenType.EMAIL_VERIFICATION,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()

    verified = client.post("/auth/verify-email", json={"token": raw_verify})
    assert verified.status_code == 200
    assert verified.json()["email_verified"] is True

    reset_request = client.post(
        "/auth/request-password-reset",
        json={"email": "verify@example.com"},
    )
    assert reset_request.status_code == 200

    token_row = db.scalar(
        select(AuthToken).where(AuthToken.token_type == AuthTokenType.PASSWORD_RESET)
    )
    assert token_row is not None
    raw_reset = generate_opaque_token()
    token_row.token_hash = hash_token(raw_reset)
    db.commit()

    reset = client.post(
        "/auth/reset-password",
        json={"token": raw_reset, "new_password": "NewSecret9"},
    )
    assert reset.status_code == 200

    old_session = client.get("/auth/me", headers=auth_header(payload["access_token"]))
    assert old_session.status_code == 401

    login = client.post(
        "/auth/login",
        json={"email": "verify@example.com", "password": "NewSecret9"},
    )
    assert login.status_code == 200


def test_one_time_token_not_reusable(client, db) -> None:
    payload = _register(client, "once@example.com")
    user_id = client.get("/auth/me", headers=auth_header(payload["access_token"])).json()["id"]

    raw_verify = generate_opaque_token()
    db.add(
        AuthToken(
            user_id=user_id,
            token_hash=hash_token(raw_verify),
            token_type=AuthTokenType.EMAIL_VERIFICATION,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()

    first = client.post("/auth/verify-email", json={"token": raw_verify})
    assert first.status_code == 200

    second = client.post("/auth/verify-email", json={"token": raw_verify})
    assert second.status_code == 400
    assert second.json()["code"] == "invalid_token"


def test_cross_user_idor(client) -> None:
    alice = _register(client, "alice@example.com")["access_token"]
    bob = _register(client, "bob@example.com")["access_token"]

    alice_id = client.get("/auth/me", headers=auth_header(alice)).json()["id"]
    bob_id = client.get("/auth/me", headers=auth_header(bob)).json()["id"]

    own = client.get(f"/users/{alice_id}", headers=auth_header(alice))
    assert own.status_code == 200

    cross = client.get(f"/users/{bob_id}", headers=auth_header(alice))
    assert cross.status_code == 403
    assert cross.json()["code"] == "forbidden"


def test_cross_league_idor(client, db) -> None:
    owner_token = _register(client, "owner@example.com")["access_token"]
    outsider_token = _register(client, "outsider@example.com")["access_token"]

    owner_id = client.get("/auth/me", headers=auth_header(owner_token)).json()["id"]

    league = League(name="Serie A Friends", season_year=2025, state=LeagueState.DRAFT)
    db.add(league)
    db.flush()
    db.add(
        LeagueMembership(
            league_id=league.id,
            user_id=owner_id,
            role=LeagueMemberRole.OWNER,
        )
    )
    db.commit()

    owner_view = client.get(f"/leagues/{league.id}", headers=auth_header(owner_token))
    assert owner_view.status_code == 200

    outsider_view = client.get(f"/leagues/{league.id}", headers=auth_header(outsider_token))
    assert outsider_view.status_code == 403
    assert outsider_view.json()["code"] == "forbidden"


def test_unauthenticated_me(client) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_create_league_requires_verified_email(client, db) -> None:
    token = _register(client, "unverified@example.com")["access_token"]
    competition_ids = [
        str(row.id)
        for row in db.scalars(select(Competition).order_by(Competition.provider_id).limit(3)).all()
    ]
    response = client.post(
        "/leagues",
        json={"name": "Blocked League", "season_year": 2025, "competition_ids": competition_ids},
        headers=auth_header(token),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"


def test_rate_limit_login(client, rate_limiter) -> None:
    from auth.rate_limit import MemoryRateLimiter

    assert isinstance(rate_limiter, MemoryRateLimiter)
    _register(client, "limited@example.com")

    for _ in range(5):
        response = client.post(
            "/auth/login",
            json={"email": "limited@example.com", "password": "WrongPass1"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login",
        json={"email": "limited@example.com", "password": "WrongPass1"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limit_exceeded"
