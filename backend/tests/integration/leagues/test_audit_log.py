"""Integration tests for the league audit log view (EP11-03)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.session import create_session_factory
from leagues.models.competition import Competition
from mail.capture import get_captured_emails


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


@pytest.fixture
def db_session(db_url: str, migrated_engine: object) -> Session:
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


def _create_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_league_admin_sees_own_league_audit_events(
    client: TestClient, competition_ids: list[str]
) -> None:
    token, owner_id = _register_and_login(client, "audit-admin@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Audit")

    response = client.get(
        f"/leagues/{league_id}/audit", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    actions = {item["action"] for item in body["items"]}
    assert "league_created" in actions
    assert body["items"][0]["actorId"] == str(owner_id)


def test_audit_log_denied_for_non_member(client: TestClient, competition_ids: list[str]) -> None:
    token, _ = _register_and_login(client, "audit-owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Audit Privata")

    outsider_token, _ = _register_and_login(client, "audit-outsider@example.com")
    response = client.get(
        f"/leagues/{league_id}/audit",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert response.status_code in (403, 404)
