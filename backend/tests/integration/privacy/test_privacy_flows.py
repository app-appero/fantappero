"""Integration tests for data export and account deletion (EP02-04)."""

from __future__ import annotations

from sqlalchemy import select
from tests.integration.auth.conftest import auth_header

from database.enums import LeagueMemberRole, LeagueState, PlatformRole, PrivacyAuditAction
from database.models.accounts import User
from database.models.leagues import League, LeagueMembership
from database.models.privacy import PrivacyAuditEvent
from privacy.anonymization import ANONYMIZED_DISPLAY_NAME, anonymized_email


def _register(client, email: str, password: str = "Secret123") -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def test_export_returns_complete_readable_bundle(client) -> None:
    token = _register(client, "export@example.com")["access_token"]

    client.patch(
        "/users/me",
        headers=auth_header(token),
        json={"display_name": "Export Player", "accept_policy": True, "policy_version": "2026-01"},
    )

    response = client.get("/users/me/export", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()

    assert body["format_version"] == "2026-01"
    assert body["account"]["email"] == "export@example.com"
    assert body["profile"]["display_name"] == "Export Player"
    assert body["profile"]["policy_version"] == "2026-01"
    assert isinstance(body["sessions"], list)
    assert len(body["sessions"]) >= 1
    assert body["competitive_summary"]["league_memberships_preserved"] == 0


def test_export_empty_league_memberships(client) -> None:
    token = _register(client, "empty-export@example.com")["access_token"]
    response = client.get("/users/me/export", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["league_memberships"] == []


def test_export_unauthenticated(client) -> None:
    response = client.get("/users/me/export")
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_session"


def test_export_creates_audit_event(client, db) -> None:
    token = _register(client, "audit-export@example.com")["access_token"]
    user_id = client.get("/auth/me", headers=auth_header(token)).json()["id"]

    client.get("/users/me/export", headers=auth_header(token))

    events = db.scalars(
        select(PrivacyAuditEvent).where(
            PrivacyAuditEvent.user_id == user_id,
            PrivacyAuditEvent.action == PrivacyAuditAction.DATA_EXPORT,
        )
    ).all()
    assert len(events) == 1
    assert events[0].actor_id == user_id


def test_delete_anonymizes_account_and_preserves_league_membership(client, db) -> None:
    password = "Secret123"
    token = _register(client, "delete@example.com", password=password)["access_token"]
    user_id = client.get("/auth/me", headers=auth_header(token)).json()["id"]

    client.patch(
        "/users/me",
        headers=auth_header(token),
        json={"display_name": "League Player"},
    )

    league = League(name="Serie A Friends", season_year=2025, state=LeagueState.DRAFT)
    db.add(league)
    db.flush()
    db.add(
        LeagueMembership(
            league_id=league.id,
            user_id=user_id,
            role=LeagueMemberRole.OWNER,
        )
    )
    db.commit()

    delete_response = client.post(
        "/users/me/delete",
        headers=auth_header(token),
        json={"password": password, "confirm": True},
    )
    assert delete_response.status_code == 200
    assert "deleted" in delete_response.json()["message"].lower()

    db.expire_all()
    user = db.get(User, user_id)
    assert user is not None
    assert user.is_deleted
    assert user.email == anonymized_email(user.id)
    assert user.profile.display_name == ANONYMIZED_DISPLAY_NAME

    membership = db.scalar(
        select(LeagueMembership).where(LeagueMembership.user_id == user_id)
    )
    assert membership is not None
    assert membership.historical_display_name == "Deleted User (L.***)"

    me_after = client.get("/auth/me", headers=auth_header(token))
    assert me_after.status_code == 401

    audit = db.scalars(
        select(PrivacyAuditEvent).where(
            PrivacyAuditEvent.user_id == user_id,
            PrivacyAuditEvent.action == PrivacyAuditAction.ACCOUNT_DELETE,
        )
    ).all()
    assert len(audit) == 1


def test_delete_wrong_password(client) -> None:
    token = _register(client, "wrong-pass@example.com")["access_token"]
    response = client.post(
        "/users/me/delete",
        headers=auth_header(token),
        json={"password": "WrongPass1", "confirm": True},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_delete_confirmation"


def test_delete_missing_confirm(client) -> None:
    token = _register(client, "no-confirm@example.com")["access_token"]
    response = client.post(
        "/users/me/delete",
        headers=auth_header(token),
        json={"password": "Secret123", "confirm": False},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_delete_confirmation"


def test_delete_already_deleted_account(client) -> None:
    password = "Secret123"
    token = _register(client, "twice@example.com", password=password)["access_token"]

    first = client.post(
        "/users/me/delete",
        headers=auth_header(token),
        json={"password": password, "confirm": True},
    )
    assert first.status_code == 200

    second = client.post(
        "/users/me/delete",
        headers=auth_header(token),
        json={"password": password, "confirm": True},
    )
    assert second.status_code == 401


def test_operator_cannot_export_other_user_data(client, db) -> None:
    user_token = _register(client, "privacy-user@example.com")["access_token"]
    operator_token = _register(client, "privacy-op@example.com")["access_token"]

    operator_id = client.get("/auth/me", headers=auth_header(operator_token)).json()["id"]
    operator = db.get(User, operator_id)
    operator.platform_role = PlatformRole.OPERATOR
    db.add(operator)
    db.commit()

    response = client.get("/users/me/export", headers=auth_header(operator_token))
    assert response.status_code == 200

    user_id = client.get("/auth/me", headers=auth_header(user_token)).json()["id"]
    cross = client.get(f"/users/{user_id}/export", headers=auth_header(operator_token))
    assert cross.status_code == 404
