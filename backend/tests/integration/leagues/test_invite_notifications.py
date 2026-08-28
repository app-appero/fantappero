"""Notifica invito e badge inviti pendenti (EP13-P07)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user_profile import UserProfile
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.named_league_invite import NamedLeagueInvite
from mail.capture import get_captured_emails
from notifications.models import Notification


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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


def _make_available(db_session: Session, user_id: UUID) -> None:
    """Un utente è invitabile solo se si è reso disponibile (default: no)."""
    profile = db_session.scalars(
        select(UserProfile).where(UserProfile.user_id == user_id)
    ).one()
    profile.available_for_invites = True
    db_session.commit()


def _invite(client: TestClient, token: str, league_id: str, recipient_id: UUID) -> dict:
    response = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {token}"},
        json={"recipientUserId": str(recipient_id)},
    )
    return response


def _pending_count(client: TestClient, token: str) -> int:
    response = client.get(
        "/leagues/inviti-ricevuti/conteggio",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return response.json()["pendingInviteCount"]


def test_named_invite_creates_exactly_one_notification(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "inv-admin@example.com")
    guest_token, guest_id = _register_and_login(client, "inv-guest@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Inviti")
    _make_available(db_session, guest_id)

    response = _invite(client, admin_token, league_id, guest_id)
    assert response.status_code in (200, 201)

    notifications = db_session.scalars(
        select(Notification).where(Notification.user_id == guest_id)
    ).all()
    invite_notifications = [
        item for item in notifications if item.template_key == "sistema.invito_lega"
    ]
    assert len(invite_notifications) == 1
    assert invite_notifications[0].deep_link == "/inviti"
    assert "Lega Inviti" in invite_notifications[0].body


def test_new_invite_increments_the_pending_badge_by_one(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "badge-admin@example.com")
    guest_token, guest_id = _register_and_login(client, "badge-guest@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Badge")
    _make_available(db_session, guest_id)

    assert _pending_count(client, guest_token) == 0
    _invite(client, admin_token, league_id, guest_id)
    assert _pending_count(client, guest_token) == 1


def test_reading_the_notification_does_not_close_the_invite(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Il punto della card: i due conteggi sono distinti."""
    admin_token, _ = _register_and_login(client, "read-admin@example.com")
    guest_token, guest_id = _register_and_login(client, "read-guest@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lettura")
    _make_available(db_session, guest_id)
    _invite(client, admin_token, league_id, guest_id)

    notification = db_session.scalars(
        select(Notification).where(
            Notification.user_id == guest_id,
            Notification.template_key == "sistema.invito_lega",
        )
    ).one()

    marked = client.post(
        f"/notifications/{notification.id}/read",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert marked.status_code == 200

    # La notifica è letta, ma l'invito resta da decidere.
    assert _pending_count(client, guest_token) == 1


def test_accepting_an_invite_reconciles_the_badge(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "acc-admin@example.com")
    guest_token, guest_id = _register_and_login(client, "acc-guest@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Accetta")
    _make_available(db_session, guest_id)
    _invite(client, admin_token, league_id, guest_id)
    assert _pending_count(client, guest_token) == 1

    received = client.get(
        "/leagues/inviti-ricevuti",
        headers={"Authorization": f"Bearer {guest_token}"},
    ).json()
    invite_id = received[0]["id"]

    accepted = client.post(
        f"/leagues/inviti-ricevuti/{invite_id}/accetta",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert accepted.status_code == 200
    assert _pending_count(client, guest_token) == 0


def test_declining_an_invite_reconciles_the_badge(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "dec-admin@example.com")
    guest_token, guest_id = _register_and_login(client, "dec-guest@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Rifiuta")
    _make_available(db_session, guest_id)
    _invite(client, admin_token, league_id, guest_id)

    received = client.get(
        "/leagues/inviti-ricevuti",
        headers={"Authorization": f"Bearer {guest_token}"},
    ).json()
    declined = client.post(
        f"/leagues/inviti-ricevuti/{received[0]['id']}/rifiuta",
        headers={"Authorization": f"Bearer {guest_token}"},
    )
    assert declined.status_code == 200
    assert _pending_count(client, guest_token) == 0


def test_expired_invite_does_not_count_towards_the_badge(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "exp-admin@example.com")
    guest_token, guest_id = _register_and_login(client, "exp-guest@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scaduti")
    _make_available(db_session, guest_id)
    _invite(client, admin_token, league_id, guest_id)
    assert _pending_count(client, guest_token) == 1

    # Un CHECK impedisce `expires_at` prima di `created_at`: si simula un
    # invito vecchio, retrodatando entrambi.
    invite = db_session.scalars(
        select(NamedLeagueInvite).where(NamedLeagueInvite.recipient_id == guest_id)
    ).one()
    invite.created_at = datetime.now(UTC) - timedelta(days=10)
    invite.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()

    assert _pending_count(client, guest_token) == 0


def test_count_is_scoped_to_the_requesting_user(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Il badge di una persona non deve contare gli inviti di un'altra."""
    admin_token, _ = _register_and_login(client, "scope-admin@example.com")
    guest_token, guest_id = _register_and_login(client, "scope-guest@example.com")
    other_token, _ = _register_and_login(client, "scope-other@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Perimetro")
    _make_available(db_session, guest_id)
    _invite(client, admin_token, league_id, guest_id)

    assert _pending_count(client, guest_token) == 1
    assert _pending_count(client, other_token) == 0
