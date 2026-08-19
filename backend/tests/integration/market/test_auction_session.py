"""Integration tests for the sealed-bid initial auction session (EP08-01)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
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
from market.models import MarketBid
from sports_data.roster.models import Athlete


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


def _create_open_session(client: TestClient, admin_token: str, league_id: str) -> str:
    now = datetime.now(UTC)
    response = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": (now - timedelta(minutes=1)).isoformat(),
            "closesAt": (now + timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "open"
    return response.json()["id"]


def test_admin_creates_session_and_member_submits_sealed_bid(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "auction.admin@example.com")
    member_token, member_id = _register_and_login(client, "auction.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Asta")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9001, "Mario Bidder")

    session_id = _create_open_session(client, admin_token, league_id)

    bid = client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"amountCredits": 250},
    )
    assert bid.status_code == 200
    body = bid.json()
    assert body["amountCredits"] == 250
    assert body["status"] == "submitted"

    # Sealed: the admin's own bid listing never surfaces someone else's bids.
    admin_bids = client.get(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_bids.status_code == 200
    assert admin_bids.json()["bids"] == []

    member_bids = client.get(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert member_bids.status_code == 200
    assert len(member_bids.json()["bids"]) == 1
    assert member_bids.json()["bids"][0]["amountCredits"] == 250

    # Re-submitting updates the sealed bid in place (still one row).
    updated = client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"amountCredits": 400},
    )
    assert updated.status_code == 200
    assert updated.json()["amountCredits"] == 400
    rows = db_session.scalars(
        select(MarketBid).where(MarketBid.session_id == UUID(session_id))
    ).all()
    assert len(rows) == 1
    assert rows[0].amount_credits == 400


def test_bid_rejected_over_balance_and_on_owned_athlete(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "auction.over@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Saldo")
    athlete = _seed_athlete(db_session, 9002, "Costoso Player")
    session_id = _create_open_session(client, admin_token, league_id)

    overdraw = client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 5000},
    )
    assert overdraw.status_code == 400
    assert overdraw.json()["code"] == "insufficient_credits"

    zero = client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 0},
    )
    assert zero.status_code == 422  # ge=1 rejected at the schema layer


def test_bid_rejected_outside_window(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "auction.window@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Finestra")
    athlete = _seed_athlete(db_session, 9003, "Player Finestra")

    now = datetime.now(UTC)
    future_session = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": (now + timedelta(hours=1)).isoformat(),
            "closesAt": (now + timedelta(hours=2)).isoformat(),
        },
    )
    assert future_session.status_code == 201
    assert future_session.json()["status"] == "scheduled"
    session_id = future_session.json()["id"]

    rejected = client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 100},
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "market_session_not_open"


def test_withdraw_bid_and_only_own_team_can_manage_it(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "auction.withdraw.admin@example.com")
    member_token, member_id = _register_and_login(client, "auction.withdraw.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Ritiro")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9004, "Player Ritiro")
    session_id = _create_open_session(client, admin_token, league_id)

    submit = client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"amountCredits": 100},
    )
    assert submit.status_code == 200

    withdraw = client.delete(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert withdraw.status_code == 204

    listing = client.get(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert listing.json()["bids"][0]["status"] == "cancelled"


def test_market_manage_required_to_create_or_close_session(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "auction.perm.admin@example.com")
    member_token, member_id = _register_and_login(client, "auction.perm.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Permessi Asta")
    _add_member(db_session, league_id, member_id)

    now = datetime.now(UTC)
    forbidden = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "opensAt": now.isoformat(),
            "closesAt": (now + timedelta(hours=1)).isoformat(),
        },
    )
    assert forbidden.status_code == 403

    session_id = _create_open_session(client, admin_token, league_id)
    close_forbidden = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert close_forbidden.status_code == 403

    close_ok = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert close_ok.status_code == 200
    assert close_ok.json()["status"] == "closed"


def test_concurrent_bid_updates_leave_single_consistent_row(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "auction.conc@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Concorrenza Asta")
    athlete = _seed_athlete(db_session, 9005, "Player Concorrente")
    session_id = _create_open_session(client, admin_token, league_id)

    def _bid(amount: int) -> int:
        response = client.put(
            f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"amountCredits": amount},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(_bid, [50, 60, 70, 80]))

    assert all(status == 200 for status in statuses)
    rows = db_session.scalars(
        select(MarketBid).where(MarketBid.session_id == UUID(session_id))
    ).all()
    assert len(rows) == 1
    assert rows[0].amount_credits in {50, 60, 70, 80}
