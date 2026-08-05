"""Integration coverage for EP03-04 participant management."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueAuditAction, LeagueMemberRole, LeagueState
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
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


@pytest.fixture
def competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    return [str(row.id) for row in rows[:3]]


def _create_league(
    client: TestClient,
    token: str,
    competition_ids: list[str],
    name: str,
) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_member(db_session: Session, league_id: str, user_id: UUID) -> None:
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id),
            user_id=user_id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    db_session.commit()


def test_list_members_requires_admin(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "members.owner@example.com")
    member_token, member_id = _register_and_login(client, "members.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Partecipanti")
    _add_member(db_session, league_id, member_id)

    response = client.get(
        f"/leagues/{league_id}/amministrazione/partecipanti",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    forbidden = client.get(
        f"/leagues/{league_id}/amministrazione/partecipanti",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert response.status_code == 200
    assert {row["userId"] for row in response.json()} == {str(owner_id), str(member_id)}
    assert {row["role"] for row in response.json()} == {"league_admin", "member"}
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "forbidden"


def test_remove_member_is_atomic_and_cannot_remove_admin(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "remove.owner@example.com")
    _, member_id = _register_and_login(client, "remove.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Rimozione")
    _add_member(db_session, league_id, member_id)
    url = f"/leagues/{league_id}/amministrazione/partecipanti"

    blocked = client.delete(
        f"{url}/{owner_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    removed = client.delete(
        f"{url}/{member_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    repeated = client.delete(
        f"{url}/{member_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert blocked.status_code == 400
    assert blocked.json()["code"] == "cannot_remove_admin"
    assert removed.status_code == 200
    assert removed.json()["userId"] == str(member_id)
    assert repeated.status_code == 400
    assert repeated.json()["code"] == "member_not_found"
    assert (
        db_session.scalar(
            select(func.count(LeagueMembership.id)).where(
                LeagueMembership.league_id == UUID(league_id),
                LeagueMembership.role == LeagueMemberRole.OWNER,
            )
        )
        == 1
    )
    assert (
        db_session.scalar(
            select(func.count(LeagueAuditEvent.id)).where(
                LeagueAuditEvent.league_id == UUID(league_id),
                LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_MEMBER_REMOVED,
            )
        )
        == 1
    )


def test_transfer_admin_is_atomic_idempotent_and_draft_only(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "transfer.owner@example.com")
    member_token, member_id = _register_and_login(client, "transfer.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Trasferimento")
    _add_member(db_session, league_id, member_id)
    transfer_url = (
        f"/leagues/{league_id}/amministrazione/partecipanti/{member_id}/trasferimento-admin"
    )

    transferred = client.post(
        transfer_url,
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    repeated = client.post(
        transfer_url,
        headers={"Authorization": f"Bearer {member_token}"},
    )
    former_owner_forbidden = client.get(
        f"/leagues/{league_id}/amministrazione/partecipanti",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert transferred.status_code == 200
    assert transferred.json()["role"] == "league_admin"
    assert repeated.status_code == 200
    assert former_owner_forbidden.status_code == 403
    db_session.expire_all()
    roles = dict(
        db_session.execute(
            select(LeagueMembership.user_id, LeagueMembership.role).where(
                LeagueMembership.league_id == UUID(league_id)
            )
        ).all()
    )
    assert roles == {
        owner_id: LeagueMemberRole.MEMBER,
        member_id: LeagueMemberRole.OWNER,
    }
    assert (
        db_session.scalar(
            select(func.count(LeagueAuditEvent.id)).where(
                LeagueAuditEvent.league_id == UUID(league_id),
                LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_ADMIN_TRANSFERRED,
            )
        )
        == 1
    )

    league = db_session.get(League, UUID(league_id))
    assert league is not None
    league.state = LeagueState.ACTIVE
    db_session.commit()
    blocked = client.delete(
        f"/leagues/{league_id}/amministrazione/partecipanti/{owner_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "league_not_draft"
