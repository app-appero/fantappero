"""Integration coverage for EP03-03 invitation lifecycle."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from auth.models.user_profile import UserProfile
from database.enums import LeagueAuditAction, LeagueMemberRole, PlatformRole, UserType
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_invite import LeagueInvite
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.models.named_league_invite import NamedLeagueInvite
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


def _create_invite(client: TestClient, token: str, league_id: str) -> dict[str, object]:
    response = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {token}"},
        json={"expiresInDays": 7},
    )
    assert response.status_code == 201
    return response.json()


def test_create_list_accept_and_idempotency(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "invite.owner@example.com")
    member_token, member_id = _register_and_login(client, "invite.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Inviti")

    created = _create_invite(client, owner_token, league_id)
    assert created["status"] == "active"
    assert created["code"]
    assert f"/leghe/invito?token={created['token']}" in str(created["inviteUrl"])

    listing = client.get(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == created["id"]
    assert "token" not in listing.json()[0]
    assert "code" not in listing.json()[0]

    accepted = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"code": str(created["code"]).lower()},
    )
    repeated = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"token": created["token"]},
    )
    assert accepted.status_code == 200
    assert accepted.json()["alreadyMember"] is False
    assert repeated.status_code == 200
    assert repeated.json()["alreadyMember"] is True

    membership_count = db_session.scalar(
        select(func.count(LeagueMembership.id)).where(
            LeagueMembership.league_id == UUID(league_id),
            LeagueMembership.user_id == member_id,
        )
    )
    assert membership_count == 1
    # Creazione lega e accettazione invito provisionano anche squadra fantasy
    # e conto crediti per owner/membro (M3-1): filtra sulle tre azioni di
    # interesse per questo test.
    audits = db_session.scalars(
        select(LeagueAuditEvent)
        .where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action.in_(
                [
                    LeagueAuditAction.LEAGUE_CREATED,
                    LeagueAuditAction.LEAGUE_INVITE_CREATED,
                    LeagueAuditAction.LEAGUE_MEMBER_JOINED,
                ]
            ),
        )
        .order_by(LeagueAuditEvent.created_at.asc())
    ).all()
    assert [audit.action for audit in audits] == [
        LeagueAuditAction.LEAGUE_CREATED,
        LeagueAuditAction.LEAGUE_INVITE_CREATED,
        LeagueAuditAction.LEAGUE_MEMBER_JOINED,
    ]
    assert audits[1].actor_id == owner_id
    assert audits[2].actor_id == member_id


def test_revoked_and_expired_invites_are_rejected(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "invite.revoke.owner@example.com")
    member_token, _ = _register_and_login(client, "invite.revoke.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Revoca")

    revoked_invite = _create_invite(client, owner_token, league_id)
    first_revoke = client.delete(
        f"/leagues/{league_id}/amministrazione/inviti/{revoked_invite['id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    second_revoke = client.delete(
        f"/leagues/{league_id}/amministrazione/inviti/{revoked_invite['id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert first_revoke.status_code == 200
    assert first_revoke.json()["status"] == "revoked"
    assert second_revoke.status_code == 200

    rejected = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"token": revoked_invite["token"]},
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "invite_revoked"

    expired_invite = _create_invite(client, owner_token, league_id)
    persisted = db_session.get(LeagueInvite, UUID(str(expired_invite["id"])))
    assert persisted is not None
    persisted.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()
    expired = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"token": expired_invite["token"]},
    )
    assert expired.status_code == 400
    assert expired.json()["code"] == "invite_expired"


def test_capacity_failure_is_atomic(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "invite.full.owner@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Piena")
    rules = db_session.scalar(select(LeagueRules).where(LeagueRules.league_id == UUID(league_id)))
    assert rules is not None
    rules.participant_count = 4

    for index in range(3):
        _, user_id = _register_and_login(client, f"invite.full.member{index}@example.com")
        db_session.add(
            LeagueMembership(
                league_id=UUID(league_id),
                user_id=user_id,
                role=LeagueMemberRole.MEMBER,
            )
        )
    db_session.commit()

    joining_token, joining_id = _register_and_login(client, "invite.full.joining@example.com")
    invite = _create_invite(client, owner_token, league_id)
    response = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {joining_token}"},
        json={"token": invite["token"]},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "league_full"
    assert (
        db_session.scalar(
            select(func.count(LeagueMembership.id)).where(
                LeagueMembership.league_id == UUID(league_id),
                LeagueMembership.user_id == joining_id,
            )
        )
        == 0
    )
    assert (
        db_session.scalar(
            select(func.count(LeagueAuditEvent.id)).where(
                LeagueAuditEvent.league_id == UUID(league_id),
                LeagueAuditEvent.actor_id == joining_id,
                LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_MEMBER_JOINED,
            )
        )
        == 0
    )


def test_invite_management_requires_admin_and_enabled_option(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "invite.permissions.owner@example.com")
    member_token, member_id = _register_and_login(client, "invite.permissions.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Permessi Inviti")
    db_session.add(
        LeagueMembership(
            league_id=UUID(league_id),
            user_id=member_id,
            role=LeagueMemberRole.MEMBER,
        )
    )
    db_session.commit()

    forbidden = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"expiresInDays": 7},
    )
    assert forbidden.status_code == 403

    rules = db_session.scalar(select(LeagueRules).where(LeagueRules.league_id == UUID(league_id)))
    assert rules is not None
    rules.allow_manual_invites = False
    db_session.commit()
    disabled = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"expiresInDays": 7},
    )
    assert disabled.status_code == 400
    assert disabled.json()["code"] == "manual_invites_disabled"


def test_named_invite_directory_accept_and_idempotency(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "named.owner@example.com")
    recipient_token, recipient_id = _register_and_login(client, "named.recipient@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Nominativa")

    profile_update = client.patch(
        "/profile/me",
        headers={"Authorization": f"Bearer {recipient_token}"},
        json={"availableForInvites": True},
    )
    assert profile_update.status_code == 200
    assert profile_update.json()["availableForInvites"] is True

    directory = client.get(
        f"/leagues/{league_id}/amministrazione/fantallenatori",
        headers={"Authorization": f"Bearer {owner_token}"},
        params={"search": "named.recipient", "pageSize": 10},
    )
    assert directory.status_code == 200
    item = next(row for row in directory.json()["items"] if row["userId"] == str(recipient_id))
    assert item["userType"] == "human"
    assert item["availableForInvites"] is True
    assert "email" not in item
    assert "@" not in item["displayName"]

    created = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(recipient_id)},
    )
    assert created.status_code == 201
    invite_id = created.json()["id"]
    assert created.json()["status"] == "pending"
    assert (
        db_session.scalar(
            select(func.count(LeagueAuditEvent.id)).where(
                LeagueAuditEvent.league_id == UUID(league_id),
                LeagueAuditEvent.action == LeagueAuditAction.NAMED_INVITE_CREATED,
            )
        )
        == 1
    )

    received = client.get(
        "/leagues/inviti-ricevuti",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert received.status_code == 200
    assert received.json()[0]["id"] == invite_id

    accepted = client.post(
        f"/leagues/inviti-ricevuti/{invite_id}/accetta",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    repeated = client.post(
        f"/leagues/inviti-ricevuti/{invite_id}/accetta",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["alreadyProcessed"] is False
    assert repeated.status_code == 200
    assert repeated.json()["alreadyProcessed"] is True
    assert (
        db_session.scalar(
            select(func.count(LeagueMembership.id)).where(
                LeagueMembership.league_id == UUID(league_id),
                LeagueMembership.user_id == recipient_id,
            )
        )
        == 1
    )

    received_after = client.get(
        "/leagues/inviti-ricevuti",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert received_after.status_code == 200
    assert received_after.json() == []


def test_ai_named_invite_auto_accepts_and_ai_cannot_login(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    from auth.security import hash_password

    owner_token, _ = _register_and_login(client, "named.ai.owner@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega IA")
    ai = User(
        email="named-ai@example.com",
        password_hash=hash_password("Password123!"),
        platform_role=PlatformRole.USER,
        user_type=UserType.AI,
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(ai)
    db_session.flush()
    db_session.add(
        UserProfile(
            user_id=ai.id,
            display_name="Mister IA",
            available_for_invites=True,
        )
    )
    db_session.commit()

    created = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(ai.id)},
    )
    assert created.status_code == 201
    assert created.json()["status"] == "accepted"
    assert created.json()["autoAccepted"] is True
    assert (
        db_session.scalar(
            select(func.count(LeagueMembership.id)).where(
                LeagueMembership.league_id == UUID(league_id),
                LeagueMembership.user_id == ai.id,
            )
        )
        == 1
    )
    persisted = db_session.get(NamedLeagueInvite, UUID(created.json()["id"]))
    assert persisted is not None

    login = client.post(
        "/auth/login",
        json={"email": ai.email, "password": "Password123!"},
    )
    assert login.status_code == 401


def test_named_invite_decline_is_idempotent(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "named.decline.owner@example.com")
    recipient_token, recipient_id = _register_and_login(
        client,
        "named.decline.recipient@example.com",
    )
    league_id = _create_league(client, owner_token, competition_ids, "Lega Rifiuto")
    available = client.patch(
        "/profile/me",
        headers={"Authorization": f"Bearer {recipient_token}"},
        json={"availableForInvites": True},
    )
    assert available.status_code == 200
    created = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(recipient_id)},
    )
    assert created.status_code == 201
    endpoint = f"/leagues/inviti-ricevuti/{created.json()['id']}/rifiuta"
    declined = client.post(
        endpoint,
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    repeated = client.post(
        endpoint,
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "declined"
    assert declined.json()["alreadyProcessed"] is False
    assert repeated.status_code == 200
    assert repeated.json()["alreadyProcessed"] is True


def test_link_invite_respects_named_slot_reservation(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "reserved.owner@example.com")
    reserved_token, reserved_id = _register_and_login(client, "reserved.coach@example.com")
    outsider_token, _ = _register_and_login(client, "reserved.outsider@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Prenotazioni")
    rules = db_session.scalar(select(LeagueRules).where(LeagueRules.league_id == UUID(league_id)))
    assert rules is not None
    rules.participant_count = 4
    for index in range(2):
        _, filler_id = _register_and_login(client, f"reserved.filler{index}@example.com")
        db_session.add(
            LeagueMembership(
                league_id=UUID(league_id),
                user_id=filler_id,
                role=LeagueMemberRole.MEMBER,
            )
        )
    profile = db_session.get(UserProfile, reserved_id)
    assert profile is not None
    profile.available_for_invites = True
    db_session.commit()

    named = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"recipientUserId": str(reserved_id)},
    )
    assert named.status_code == 201
    link = _create_invite(client, owner_token, league_id)

    rejected = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {outsider_token}"},
        json={"token": link["token"]},
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "league_full"

    accepted = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {reserved_token}"},
        json={"token": link["token"]},
    )
    assert accepted.status_code == 200
    persisted = db_session.get(NamedLeagueInvite, UUID(named.json()["id"]))
    assert persisted is not None
    db_session.refresh(persisted)
    assert persisted.status.value == "accepted"
