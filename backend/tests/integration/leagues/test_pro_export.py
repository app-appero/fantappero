"""Integration tests for the Pro-gated league export (EP11-05)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from billing.entitlement_service import EntitlementService
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


def test_export_requires_pro_entitlement(client: TestClient, competition_ids: list[str]) -> None:
    token, _ = _register_and_login(client, "export-free@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Export Free")

    response = client.get(
        f"/leagues/{league_id}/pro/export", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "pro_entitlement_required"


def test_export_succeeds_for_pro_user(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "export-pro@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Export Pro")

    EntitlementService(db_session).activate_pro_until(
        user_id, until=datetime.now(UTC) + timedelta(days=30)
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/pro/export", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["leagueId"] == league_id
    assert isinstance(body["standings"], list)
    assert body["auditEventsCount"] >= 1
