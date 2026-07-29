"""Integration tests for league configuration flows (EP03-01)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from tests.integration.auth.conftest import auth_header

from auth.tokens import generate_opaque_token, hash_token
from database.enums import AuthTokenType, LeagueAuditAction, LeagueMemberRole, LeagueState
from database.models.accounts import AuthToken
from database.models.competitions import Competition
from database.models.league_audit import LeagueAuditEvent
from database.models.leagues import League, LeagueMembership


def _register(client, email: str, password: str = "Secret123") -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def _verify_user(client, db, token: str) -> str:
    from datetime import UTC, datetime, timedelta

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
    assert len(rows) >= count
    return [str(row.id) for row in rows]


def _create_league_payload(db, *, name: str = "Draft League", season_year: int = 2025) -> dict:
    return {
        "name": name,
        "season_year": season_year,
        "competition_ids": _competition_ids(db),
    }


def test_list_competitions_requires_auth(client) -> None:
    response = client.get("/leagues/competitions")
    assert response.status_code == 401


def test_list_competitions_returns_catalog(client, db) -> None:
    token = _register(client, "catalog@example.com")["access_token"]
    response = client.get("/leagues/competitions", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 5
    provider_ids = {item["provider_id"] for item in body}
    assert provider_ids == {39, 61, 78, 135, 140}


def test_create_league_draft_with_owner_and_audit(client, db) -> None:
    token = _register(client, "creator@example.com")["access_token"]
    _verify_user(client, db, token)

    payload = _create_league_payload(db, name="  My Draft League  ")
    response = client.post("/leagues", json=payload, headers=auth_header(token))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "My Draft League"
    assert body["season_year"] == 2025
    assert body["state"] == "draft"
    assert body["role"] == "owner"
    assert len(body["competitions"]) == 3

    audit = db.scalars(
        select(LeagueAuditEvent).where(LeagueAuditEvent.league_id == uuid.UUID(body["id"]))
    ).all()
    assert len(audit) == 1
    assert audit[0].action == LeagueAuditAction.LEAGUE_CREATED


def test_create_league_validation_too_few_competitions(client, db) -> None:
    token = _register(client, "few@example.com")["access_token"]
    _verify_user(client, db, token)

    competition_id = _competition_ids(db, count=1)[0]
    response = client.post(
        "/leagues",
        json={"name": "Invalid", "season_year": 2025, "competition_ids": [competition_id]},
        headers=auth_header(token),
    )
    assert response.status_code == 422


def test_create_league_domain_validation_error(client, db) -> None:
    token = _register(client, "domain@example.com")["access_token"]
    _verify_user(client, db, token)

    payload = _create_league_payload(db)
    payload["season_year"] = 2010
    response = client.post("/leagues", json=payload, headers=auth_header(token))
    assert response.status_code == 400
    assert response.json()["code"] == "league_validation_error"


def test_create_league_requires_verified_email(client, db) -> None:
    token = _register(client, "unverified@example.com")["access_token"]
    response = client.post(
        "/leagues",
        json=_create_league_payload(db),
        headers=auth_header(token),
    )
    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"


def test_get_league_returns_configuration(client, db) -> None:
    token = _register(client, "reader@example.com")["access_token"]
    _verify_user(client, db, token)

    created = client.post(
        "/leagues",
        json=_create_league_payload(db),
        headers=auth_header(token),
    ).json()

    fetched = client.get(f"/leagues/{created['id']}", headers=auth_header(token))
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["state"] == "draft"
    assert body["season_year"] == 2025
    assert len(body["competitions"]) == 3


def test_migration_seeded_competitions_are_unique(db) -> None:
    rows = db.scalars(select(Competition)).all()
    assert len(rows) == 5
    assert len({row.provider_id for row in rows}) == 5


def test_league_competitions_join_enforces_minimum_via_service(client, db) -> None:
    owner_token = _register(client, "join@example.com")["access_token"]
    owner_id = _verify_user(client, db, owner_token)

    league = League(name="Legacy", season_year=2025, state=LeagueState.DRAFT)
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

    response = client.get(f"/leagues/{league.id}", headers=auth_header(owner_token))
    assert response.status_code == 200
    assert response.json()["competitions"] == []
