"""Integration coverage for EP03-05-EXT draft league hard-delete."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueAuditAction, LeagueState
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league import League
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
    assert len(rows) >= 3
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


def test_admin_can_delete_draft_league(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, owner_id = _register_and_login(client, "delete.owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Da Eliminare")

    response = client.delete(
        f"/leagues/{league_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204

    db_session.expire_all()
    assert db_session.get(League, UUID(league_id)) is None
    audits = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.action == LeagueAuditAction.LEAGUE_DELETED,
        )
    ).all()
    assert len(audits) == 1
    assert audits[0].actor_id == owner_id
    assert audits[0].league_id is None
    assert audits[0].details == {
        "leagueId": league_id,
        "name": "Lega Da Eliminare",
        "state": "configuring",
        "seasonYear": 2026,
    }


def test_admin_delete_notifies_other_participants(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 19/11: se la lega la elimina il suo amministratore, i partecipanti non
    ricevevano «Lega eliminata» (arrivava solo con l'eliminazione da operatore)."""
    from notifications.models import Notification

    owner_token, owner_id = _register_and_login(client, "delete.notify.owner@example.com")
    member_token, member_id = _register_and_login(client, "delete.notify.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Avvisata")

    invite = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"expiresInDays": 7},
    )
    assert invite.status_code == 201
    accepted = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"token": invite.json()["token"]},
    )
    assert accepted.status_code == 200

    response = client.delete(
        f"/leagues/{league_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 204

    db_session.expire_all()
    member_notes = db_session.scalars(
        select(Notification).where(
            Notification.user_id == member_id,
            Notification.template_key == "lega.eliminata",
        )
    ).all()
    assert len(member_notes) == 1
    note = member_notes[0]
    assert note.title == "Lega eliminata"
    assert note.body == "La lega Lega Avvisata è stata eliminata dall'amministratore della lega."
    assert note.deep_link == "/"
    # Chi elimina la lega non riceve l'avviso della propria azione.
    owner_notes = db_session.scalars(
        select(Notification).where(
            Notification.user_id == owner_id,
            Notification.template_key == "lega.eliminata",
        )
    ).all()
    assert owner_notes == []


def _make_available(db_session: Session, user_id: UUID) -> None:
    from auth.models.user_profile import UserProfile

    profile = db_session.scalars(select(UserProfile).where(UserProfile.user_id == user_id)).one()
    profile.available_for_invites = True
    db_session.commit()


def _named_invite(client: TestClient, token: str, league_id: str, recipient_id: UUID) -> None:
    response = client.post(
        f"/leagues/{league_id}/amministrazione/inviti-nominativi",
        headers={"Authorization": f"Bearer {token}"},
        json={"recipientUserId": str(recipient_id)},
    )
    assert response.status_code in (200, 201), response.text


def test_admin_delete_withdraws_pending_named_invites_and_tells_the_invitees(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 21→22/11: la notifica «Nuovo invito» restava dopo l'eliminazione della lega e
    portava a «Inviti ricevuti» vuoti; l'invitato non riceveva «Lega eliminata»."""
    from datetime import UTC, datetime, timedelta

    from leagues.models.named_league_invite import NamedLeagueInvite
    from notifications.models import Notification

    owner_token, owner_id = _register_and_login(client, "delete.invite.owner@example.com")
    _, guest_id = _register_and_login(client, "delete.invite.guest@example.com")
    _, late_id = _register_and_login(client, "delete.invite.late@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Con Inviti")
    other_league_id = _create_league(client, owner_token, competition_ids, "Lega Che Resta")
    for user_id in (guest_id, late_id):
        _make_available(db_session, user_id)
    _named_invite(client, owner_token, league_id, guest_id)
    _named_invite(client, owner_token, league_id, late_id)
    _named_invite(client, owner_token, other_league_id, guest_id)
    # L'invito a «late» è scaduto ma non ancora segnato come tale.
    late_invite = db_session.scalars(
        select(NamedLeagueInvite).where(
            NamedLeagueInvite.league_id == UUID(league_id),
            NamedLeagueInvite.recipient_id == late_id,
        )
    ).one()
    late_invite.created_at = datetime.now(UTC) - timedelta(days=10)
    late_invite.expires_at = datetime.now(UTC) - timedelta(days=1)
    db_session.commit()

    def notes(user_id: UUID, template_key: str) -> list[Notification]:
        return list(
            db_session.scalars(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.template_key == template_key,
                )
            ).all()
        )

    assert len(notes(guest_id, "sistema.invito_lega")) == 2
    assert len(notes(late_id, "sistema.invito_lega")) == 1

    response = client.delete(
        f"/leagues/{league_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 204

    db_session.expire_all()
    # Resta solo l'invito dell'altra lega, che c'è ancora.
    guest_invites = notes(guest_id, "sistema.invito_lega")
    assert len(guest_invites) == 1
    assert "«Lega Che Resta»" in guest_invites[0].body
    deleted = notes(guest_id, "lega.eliminata")
    assert [note.body for note in deleted] == [
        "La lega Lega Con Inviti è stata eliminata dall'amministratore della lega."
    ]
    assert deleted[0].deep_link == "/"
    # Invito scaduto: la notifica si toglie, ma niente avviso per una lega che non lo riguarda più.
    assert notes(late_id, "sistema.invito_lega") == []
    assert notes(late_id, "lega.eliminata") == []
    assert notes(owner_id, "lega.eliminata") == []


def test_member_cannot_delete_league(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "delete.admin@example.com")
    member_token, _ = _register_and_login(client, "delete.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Membri")

    invite = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"expiresInDays": 7},
    )
    assert invite.status_code == 201
    accepted = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"token": invite.json()["token"]},
    )
    assert accepted.status_code == 200

    response = client.delete(
        f"/leagues/{league_id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert response.status_code == 403


def test_non_deletable_state_and_cross_league_idor(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "delete.state.owner@example.com")
    outsider_token, _ = _register_and_login(client, "delete.state.outsider@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Attiva Fake")

    league = db_session.get(League, UUID(league_id))
    assert league is not None
    league.state = LeagueState.ACTIVE
    db_session.commit()

    blocked = client.delete(
        f"/leagues/{league_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "league_not_deletable"

    idor = client.delete(
        f"/leagues/{league_id}",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert idor.status_code == 403


def test_member_can_list_participants_read_only(
    client: TestClient,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "home.owner@example.com")
    member_token, member_id = _register_and_login(client, "home.member@example.com")
    outsider_token, _ = _register_and_login(client, "home.outsider@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Home")

    invite = client.post(
        f"/leagues/{league_id}/amministrazione/inviti",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"expiresInDays": 7},
    )
    assert invite.status_code == 201
    accepted = client.post(
        "/leagues/inviti/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"code": invite.json()["code"]},
    )
    assert accepted.status_code == 200

    members = client.get(
        f"/leagues/{league_id}/partecipanti",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert members.status_code == 200
    user_ids = {row["userId"] for row in members.json()}
    assert str(owner_id) in user_ids
    assert str(member_id) in user_ids

    denied = client.get(
        f"/leagues/{league_id}/partecipanti",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert denied.status_code == 403
