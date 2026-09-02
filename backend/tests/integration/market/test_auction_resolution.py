"""Integration tests for sealed-bid auction resolution and tiebreaks (EP08-02)."""

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

from database.enums import CreditLedgerReason, FantasyRole, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import CreditAccount, CreditLedgerEntry, FantasyRosterSlot
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from market.models import MarketBid, MarketSession
from sports_data.listone.models import RoleAssignment
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


def _seed_athlete(
    db_session: Session,
    provider_id: int,
    name: str,
    *,
    role: FantasyRole = FantasyRole.A,
    season_year: int = 2026,
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=season_year,
            role=role,
            mapping_version="v1.0.0",
            provider_position_raw=role.value,
        )
    )
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
            "closesAt": (now + timedelta(minutes=1)).isoformat(),
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _bid(client: TestClient, league_id: str, session_id: str, token: str, athlete_id, amount: int):
    return client.put(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte/{athlete_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"amountCredits": amount},
    )


def _close_and_resolve(client: TestClient, league_id: str, session_id: str, admin_token: str):
    close = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert close.status_code == 200
    return client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )


def test_highest_bid_wins_and_credits_roster_are_updated(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "res.admin@example.com")
    member_token, member_id = _register_and_login(client, "res.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Risoluzione")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9101, "Vincitore Player")

    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, athlete.id, 200).status_code == 200
    assert _bid(client, league_id, session_id, member_token, athlete.id, 150).status_code == 200

    resolution = _close_and_resolve(client, league_id, session_id, admin_token)
    assert resolution.status_code == 200
    body = resolution.json()
    assert body["status"] == "resolved"
    assert len(body["outcomes"]) == 1
    outcome = body["outcomes"][0]
    assert outcome["outcome"] == "assigned"
    assert outcome["amountCredits"] == 200

    rosa = client.get(
        f"/leagues/{league_id}/rosa",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assigned_slot = next(
        (slot for slot in rosa.json()["slots"] if slot["athleteId"] == str(athlete.id)), None
    )
    assert assigned_slot is not None
    assert assigned_slot["purchaseCredits"] == 200

    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert credits.json()["balance"] == 800

    winner_slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete.id)
    )
    assert winner_slot is not None
    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == winner_slot.fantasy_team_id)
    )
    assert account is not None
    ledger_entry = db_session.scalar(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.account_id == account.id,
            CreditLedgerEntry.reason == CreditLedgerReason.MARKET_AUCTION_WIN,
        )
    )
    assert ledger_entry is not None
    assert ledger_entry.amount == -200

    member_bids = client.get(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/offerte",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert member_bids.json()["bids"][0]["status"] == "lost"


def test_tied_bids_open_a_tiebreak_session(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "res.tie.admin@example.com")
    member_token, member_id = _register_and_login(client, "res.tie.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Parità")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9102, "Conteso Player")

    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, athlete.id, 100).status_code == 200
    assert _bid(client, league_id, session_id, member_token, athlete.id, 100).status_code == 200

    resolution = _close_and_resolve(client, league_id, session_id, admin_token)
    assert resolution.status_code == 200
    outcome = resolution.json()["outcomes"][0]
    assert outcome["outcome"] == "tiebreak"
    tiebreak_id = outcome["tiebreakSessionId"]
    assert tiebreak_id is not None

    tiebreak_session = db_session.get(MarketSession, UUID(tiebreak_id))
    assert tiebreak_session is not None
    assert tiebreak_session.target_athlete_id == athlete.id
    assert tiebreak_session.parent_session_id == UUID(session_id)
    assert set(tiebreak_session.eligible_team_ids) == {
        str(row.fantasy_team_id)
        for row in db_session.scalars(
            select(MarketBid).where(MarketBid.session_id == UUID(session_id))
        ).all()
    }

    # Original tied bids are superseded, not left dangling as "submitted".
    original_bids = db_session.scalars(
        select(MarketBid).where(MarketBid.session_id == UUID(session_id))
    ).all()
    assert all(row.status.value == "expired" for row in original_bids)

    # No roster assignment happened yet for the contested athlete.
    slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete.id)
    )
    assert slot is None

    # A team outside the tie cannot bid in the tiebreak session.
    outsider_token, outsider_id = _register_and_login(client, "res.tie.outsider@example.com")
    _add_member(db_session, league_id, outsider_id)
    forbidden = _bid(client, league_id, tiebreak_id, outsider_token, athlete.id, 500)
    assert forbidden.status_code == 400
    assert forbidden.json()["code"] == "market_team_not_eligible"

    # A tied team can now rebid inside the tiebreak session.
    rebid = _bid(client, league_id, tiebreak_id, admin_token, athlete.id, 120)
    assert rebid.status_code == 200


def test_resolution_is_idempotent_and_atomic(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "res.idem.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Idempotenza")
    athlete = _seed_athlete(db_session, 9103, "Idempotente Player")

    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, athlete.id, 300).status_code == 200

    first = _close_and_resolve(client, league_id, session_id, admin_token)
    assert first.status_code == 200
    second = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert second.status_code == 200
    assert first.json() == second.json()

    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert credits.json()["balance"] == 700  # charged exactly once


def test_resolve_requires_closed_session_and_admin_permission(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "res.perm.admin@example.com")
    member_token, member_id = _register_and_login(client, "res.perm.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Permessi Risoluzione")
    _add_member(db_session, league_id, member_id)
    session_id = _create_open_session(client, admin_token, league_id)

    too_early = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert too_early.status_code == 400
    assert too_early.json()["code"] == "market_session_not_closed"

    client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    forbidden = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/risolvi",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert forbidden.status_code == 403


def test_concurrent_resolve_calls_charge_exactly_once(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "res.conc.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Concorrenza Risoluzione")
    athlete = _seed_athlete(db_session, 9104, "Concorrente Player")

    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, athlete.id, 90).status_code == 200
    client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/chiudi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    def _resolve(_index: int) -> int:
        response = client.post(
            f"/leagues/{league_id}/mercato/asta/sessioni/{session_id}/risolvi",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(_resolve, range(4)))

    assert all(status == 200 for status in statuses)

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete.id)
    )
    assert slot is not None
    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == slot.fantasy_team_id)
    )
    assert account is not None
    ledger_entries = db_session.scalars(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.account_id == account.id,
            CreditLedgerEntry.reason == CreditLedgerReason.MARKET_AUCTION_WIN,
        )
    ).all()
    assert len(ledger_entries) == 1
    assert account.balance == 1000 - 90
