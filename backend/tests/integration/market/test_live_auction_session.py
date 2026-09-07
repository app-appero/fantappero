"""Integration tests for the live/ascending auction session lifecycle (EP08-09)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import LeagueMemberRole
from database.session import create_session_factory
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from sports_data.roster.models import Athlete


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


def _add_member(db_session: Session, league_id: str, user_id: UUID) -> LeagueMembership:
    membership = LeagueMembership(
        league_id=UUID(league_id),
        user_id=user_id,
        role=LeagueMemberRole.MEMBER,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)
    return membership


def _seed_athlete(db_session: Session, provider_id: int, name: str) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def _manual_session_payload(*, operator_user_id: str | None = None) -> dict:
    now = datetime.now(UTC)
    payload = {
        "opensAt": now.isoformat(),
        "closesAt": (now + timedelta(hours=2)).isoformat(),
        "nominationMode": "manual",
        "minIncrementCredits": 10,
        "softCloseSeconds": 5,
        "lotDurationSeconds": 30,
    }
    if operator_user_id:
        payload["operatorUserId"] = operator_user_id
    return payload


def test_admin_creates_manual_session_and_starts_it(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.session.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Asta Live")

    created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_manual_session_payload(),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "scheduled"
    assert body["nominationMode"] == "manual"
    session_id = body["id"]

    started = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/avvia",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "open"


def test_sequential_mode_requires_nonempty_queue_and_manual_rejects_one(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.session.queue@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Asta Live Coda")
    athlete = _seed_athlete(db_session, 91001, "Calciatore Coda")

    empty_queue = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={**_manual_session_payload(), "nominationMode": "sequential"},
    )
    assert empty_queue.status_code == 400
    assert empty_queue.json()["code"] == "nomination_queue_required"

    manual_with_queue = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={**_manual_session_payload(), "nominationQueueAthleteIds": [str(athlete.id)]},
    )
    assert manual_with_queue.status_code == 400
    assert manual_with_queue.json()["code"] == "nomination_queue_not_allowed"

    sequential_ok = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            **_manual_session_payload(),
            "nominationMode": "sequential",
            "nominationQueueAthleteIds": [str(athlete.id)],
        },
    )
    assert sequential_ok.status_code == 201
    assert sequential_ok.json()["queueRemaining"] == 1


def test_market_manage_required_to_create_live_session(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.session.perm.admin@example.com")
    member_token, member_id = _register_and_login(client, "live.session.perm.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Asta Live Permessi")
    _add_member(db_session, league_id, member_id)

    forbidden = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {member_token}"},
        json=_manual_session_payload(),
    )
    assert forbidden.status_code == 403


def test_delegate_can_run_session_but_unrelated_member_cannot(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.session.delegate.admin@example.com")
    delegate_token, delegate_id = _register_and_login(
        client, "live.session.delegate.op@example.com"
    )
    outsider_token, outsider_id = _register_and_login(
        client, "live.session.delegate.outsider@example.com"
    )
    league_id = _create_league(client, admin_token, competition_ids, "Lega Asta Live Delegato")
    _add_member(db_session, league_id, delegate_id)
    _add_member(db_session, league_id, outsider_id)

    created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_manual_session_payload(operator_user_id=str(delegate_id)),
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert created.json()["operatorUserId"] == str(delegate_id)

    outsider_start = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/avvia",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert outsider_start.status_code == 403

    delegate_start = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/avvia",
        headers={"Authorization": f"Bearer {delegate_token}"},
    )
    assert delegate_start.status_code == 200
    assert delegate_start.json()["status"] == "open"


def test_live_and_sealed_initial_auction_are_mutually_exclusive(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Regressione: le due modalità dell'asta iniziale non possono coesistere
    attive nella stessa lega — e una volta finita la live, la sealed torna
    utilizzabile esattamente come prima (nessuna modifica di comportamento)."""
    admin_token, _ = _register_and_login(client, "live.session.exclusive@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Asta Esclusiva")

    live_created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_manual_session_payload(),
    )
    assert live_created.status_code == 201
    live_session_id = live_created.json()["id"]

    now = datetime.now(UTC)
    sealed_blocked = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"opensAt": now.isoformat(), "closesAt": (now + timedelta(hours=1)).isoformat()},
    )
    assert sealed_blocked.status_code == 400
    assert sealed_blocked.json()["code"] == "market_session_already_active"

    started = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{live_session_id}/avvia",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert started.status_code == 200
    ended = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{live_session_id}/termina",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "resolved"

    sealed_now_ok = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"opensAt": now.isoformat(), "closesAt": (now + timedelta(hours=1)).isoformat()},
    )
    assert sealed_now_ok.status_code == 201
    assert sealed_now_ok.json()["status"] == "open"


def test_list_live_sessions_excludes_sealed_sessions(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.session.list@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Asta Live Elenco")

    live_created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_manual_session_payload(),
    )
    assert live_created.status_code == 201

    live_list = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert live_list.status_code == 200
    assert len(live_list.json()) == 1
    assert live_list.json()[0]["id"] == live_created.json()["id"]

    sealed_list = client.get(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sealed_list.status_code == 200
    assert sealed_list.json() == []
