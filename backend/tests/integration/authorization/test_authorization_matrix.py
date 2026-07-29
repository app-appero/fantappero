"""Authorization matrix and IDOR regression tests (EP02-03)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from tests.integration.auth.conftest import auth_header

from auth.tokens import generate_opaque_token, hash_token
from database.enums import AuthTokenType, LeagueMemberRole, LeagueState, PlatformRole
from database.models.accounts import AuthToken, User
from database.models.competitions import Competition
from database.models.leagues import League, LeagueMembership


def _register(client, email: str, password: str = "Secret123") -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def _verify_user_simple(client, db, token: str) -> str:
    from datetime import timedelta

    user_id = client.get("/auth/me", headers=auth_header(token)).json()["id"]
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
    client.post("/auth/verify-email", json={"token": raw_verify})
    return user_id


def _competition_ids(db, count: int = 3) -> list[str]:
    rows = db.scalars(select(Competition).order_by(Competition.provider_id).limit(count)).all()
    return [str(row.id) for row in rows]


def _create_league(client, db, token: str, name: str = "Test League") -> dict:
    response = client.post(
        "/leagues",
        json={
            "name": name,
            "season_year": 2025,
            "competition_ids": _competition_ids(db),
        },
        headers=auth_header(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cross_user_profile_forbidden(client) -> None:
    alice = _register(client, "matrix-alice@example.com")["access_token"]
    bob = _register(client, "matrix-bob@example.com")["access_token"]

    bob_id = client.get("/auth/me", headers=auth_header(bob)).json()["id"]

    response = client.get(f"/users/{bob_id}", headers=auth_header(alice))
    assert response.status_code == 403
    assert response.json() == {
        "code": "forbidden",
        "message": "You do not have permission to access this resource.",
    }


def test_cross_league_read_forbidden(client, db) -> None:
    owner_token = _register(client, "league-owner@example.com")["access_token"]
    outsider_token = _register(client, "league-outsider@example.com")["access_token"]

    owner_id = client.get("/auth/me", headers=auth_header(owner_token)).json()["id"]

    league = League(name="Private League", season_year=2025, state=LeagueState.DRAFT)
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

    member_view = client.get(f"/leagues/{league.id}", headers=auth_header(owner_token))
    assert member_view.status_code == 200

    outsider_view = client.get(f"/leagues/{league.id}", headers=auth_header(outsider_token))
    assert outsider_view.status_code == 403
    assert outsider_view.json()["code"] == "forbidden"


def test_cross_league_update_forbidden_for_member(client, db) -> None:
    owner_token = _register(client, "update-owner@example.com")["access_token"]
    member_token = _register(client, "update-member@example.com")["access_token"]

    owner_id = client.get("/auth/me", headers=auth_header(owner_token)).json()["id"]
    member_id = client.get("/auth/me", headers=auth_header(member_token)).json()["id"]

    league = League(name="Managed League", season_year=2025, state=LeagueState.DRAFT)
    db.add(league)
    db.flush()
    db.add(
        LeagueMembership(
            league_id=league.id,
            user_id=owner_id,
            role=LeagueMemberRole.OWNER,
        )
    )
    db.add(
        LeagueMembership(
            league_id=league.id,
            user_id=member_id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    db.commit()

    owner_patch = client.patch(
        f"/leagues/{league.id}",
        json={"name": "Renamed by Owner"},
        headers=auth_header(owner_token),
    )
    assert owner_patch.status_code == 200
    assert owner_patch.json()["name"] == "Renamed by Owner"

    member_patch = client.patch(
        f"/leagues/{league.id}",
        json={"name": "Blocked Rename"},
        headers=auth_header(member_token),
    )
    assert member_patch.status_code == 403
    assert member_patch.json()["code"] == "forbidden"


def test_cross_league_update_forbidden_for_outsider(client, db) -> None:
    owner_token = _register(client, "patch-owner@example.com")["access_token"]
    outsider_token = _register(client, "patch-outsider@example.com")["access_token"]

    owner_id = client.get("/auth/me", headers=auth_header(owner_token)).json()["id"]

    league = League(name="Locked League", season_year=2025, state=LeagueState.DRAFT)
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

    response = client.patch(
        f"/leagues/{league.id}",
        json={"name": "Hijacked"},
        headers=auth_header(outsider_token),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_nonexistent_league_returns_not_found(client) -> None:
    token = _register(client, "missing-league@example.com")["access_token"]
    missing_id = "00000000-0000-0000-0000-000000000001"

    response = client.get(f"/leagues/{missing_id}", headers=auth_header(token))
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_platform_operator_can_read_any_league(client, db) -> None:
    owner_token = _register(client, "operator-owner@example.com")["access_token"]
    operator_token = _register(client, "operator-user@example.com")["access_token"]

    owner_id = client.get("/auth/me", headers=auth_header(owner_token)).json()["id"]
    operator_id = client.get("/auth/me", headers=auth_header(operator_token)).json()["id"]

    operator = db.get(User, operator_id)
    assert operator is not None
    operator.platform_role = PlatformRole.OPERATOR
    db.commit()

    league = League(name="Operator Visible", season_year=2025, state=LeagueState.DRAFT)
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

    response = client.get(f"/leagues/{league.id}", headers=auth_header(operator_token))
    assert response.status_code == 200
    assert response.json()["name"] == "Operator Visible"
    assert response.json()["role"] is None


def test_platform_operator_can_read_user_profile(client, db) -> None:
    owner_token = _register(client, "subject@example.com")["access_token"]
    operator_token = _register(client, "support@example.com")["access_token"]

    owner_id = client.get("/auth/me", headers=auth_header(owner_token)).json()["id"]
    operator_id = client.get("/auth/me", headers=auth_header(operator_token)).json()["id"]

    operator = db.get(User, operator_id)
    assert operator is not None
    operator.platform_role = PlatformRole.OPERATOR
    db.commit()

    read = client.get(f"/users/{owner_id}", headers=auth_header(operator_token))
    assert read.status_code == 200
    assert read.json()["email"] == "subject@example.com"


def test_create_league_success_when_verified(client, db) -> None:
    token = _register(client, "verified-creator@example.com")["access_token"]
    _verify_user_simple(client, db, token)

    league = _create_league(client, db, token, name="Verified League")
    assert league["name"] == "Verified League"
    assert league["role"] == "owner"

    fetched = client.get(f"/leagues/{league['id']}", headers=auth_header(token))
    assert fetched.status_code == 200
    assert fetched.json()["role"] == "owner"


def test_create_league_requires_verified_email(client, db) -> None:
    token = _register(client, "unverified-creator@example.com")["access_token"]
    response = client.post(
        "/leagues",
        json={
            "name": "Blocked League",
            "season_year": 2025,
            "competition_ids": _competition_ids(db),
        },
        headers=auth_header(token),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"
