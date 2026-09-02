"""Operator promote/revoke actions are audited (EP11-04)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import LeagueAuditAction, PlatformRole
from database.session import create_session_factory
from leagues.models.league_audit_event import LeagueAuditEvent
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
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
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


def test_promote_and_revoke_write_platform_audit_events(
    client: TestClient, db_session: Session
) -> None:
    operator_token, operator_id = _register_and_login(client, "audit-op@example.com")
    _promote(db_session, operator_id)
    _, target_id = _register_and_login(client, "audit-target@example.com")
    headers = {"Authorization": f"Bearer {operator_token}"}

    promote = client.post(f"/admin/users/{target_id}/promote", headers=headers)
    assert promote.status_code == 200

    promoted_event = db_session.scalar(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.action == LeagueAuditAction.PLATFORM_OPERATOR_PROMOTED,
            LeagueAuditEvent.actor_id == operator_id,
        )
    )
    assert promoted_event is not None
    assert promoted_event.league_id is None
    assert promoted_event.details is not None
    assert promoted_event.details["targetUserId"] == str(target_id)

    revoke = client.post(f"/admin/users/{target_id}/revoke", headers=headers)
    assert revoke.status_code == 200

    revoked_event = db_session.scalar(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.action == LeagueAuditAction.PLATFORM_OPERATOR_REVOKED,
            LeagueAuditEvent.actor_id == operator_id,
        )
    )
    assert revoked_event is not None
    assert revoked_event.details is not None
    assert revoked_event.details["targetUserId"] == str(target_id)
