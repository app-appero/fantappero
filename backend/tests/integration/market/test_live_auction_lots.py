"""Integration tests for live-auction lots and raises (EP08-09)."""

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

from database.enums import FantasyRole, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import FantasyRosterSlot
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from market.live_models import MarketLiveLot
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


def _start_manual_session(
    client: TestClient,
    admin_token: str,
    league_id: str,
    *,
    min_increment: int = 10,
    soft_close: int = 5,
    lot_duration: int = 30,
) -> str:
    now = datetime.now(UTC)
    created = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": now.isoformat(),
            "closesAt": (now + timedelta(hours=2)).isoformat(),
            "nominationMode": "manual",
            "minIncrementCredits": min_increment,
            "softCloseSeconds": soft_close,
            "lotDurationSeconds": lot_duration,
        },
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    started = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/avvia",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert started.status_code == 200
    return session_id


def _nominate(
    client: TestClient, admin_token: str, league_id: str, session_id: str, athlete_id
) -> dict:
    response = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"athleteId": str(athlete_id)},
    )
    assert response.status_code == 201
    return response.json()


def test_ascending_raises_and_force_sell_assign_roster_and_credits(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.lot.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Rilanci")
    _add_member(db_session, league_id, bidder_id)
    athlete = _seed_athlete(db_session, 92001, "Calciatore Rilanciato")

    session_id = _start_manual_session(client, admin_token, league_id)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    lot_id = lot["id"]
    assert lot["minimumNextAmountCredits"] == 10

    first_raise = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 10},
    )
    assert first_raise.status_code == 200
    assert first_raise.json()["currentAmountCredits"] == 10
    assert first_raise.json()["currentLeaderTeamId"] is not None
    assert first_raise.json()["minimumNextAmountCredits"] == 20

    sold = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/aggiudica",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sold.status_code == 200
    assert sold.json()["status"] == "sold"

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete.id)
    )
    assert slot is not None
    assert slot.purchase_credits == 10

    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert credits.status_code == 200
    assert credits.json()["balance"] == 990


def test_raise_rejected_below_minimum_and_when_already_leader(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.min.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.lot.min.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Minimo")
    _add_member(db_session, league_id, bidder_id)
    athlete = _seed_athlete(db_session, 92002, "Calciatore Minimo")

    session_id = _start_manual_session(client, admin_token, league_id, min_increment=10)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    lot_id = lot["id"]

    too_low = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 5},
    )
    assert too_low.status_code == 400
    assert too_low.json()["code"] == "market_live_raise_stale"

    ok = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 10},
    )
    assert ok.status_code == 200

    self_raise = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 20},
    )
    assert self_raise.status_code == 400
    assert self_raise.json()["code"] == "market_live_already_leader"


def test_raise_rejected_over_balance(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.balance.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Saldo")
    athlete = _seed_athlete(db_session, 92003, "Calciatore Costoso")

    session_id = _start_manual_session(client, admin_token, league_id)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    lot_id = lot["id"]

    overdraw = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amountCredits": 5000},
    )
    assert overdraw.status_code == 400
    assert overdraw.json()["code"] == "insufficient_credits"


def test_operator_actions_forbidden_for_plain_member_but_raise_allowed(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.perm.admin@example.com")
    member_token, member_id = _register_and_login(client, "live.lot.perm.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Permessi")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 92004, "Calciatore Permessi")

    session_id = _start_manual_session(client, admin_token, league_id)

    member_nominate = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"athleteId": str(athlete.id)},
    )
    assert member_nominate.status_code == 403

    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    lot_id = lot["id"]

    member_raise = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
        headers={"Authorization": f"Bearer {member_token}"},
        json={"amountCredits": 10},
    )
    assert member_raise.status_code == 200

    member_force_sell = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/aggiudica",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert member_force_sell.status_code == 403


def test_cancel_lot_allowed_before_raises_rejected_after(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.cancel.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.lot.cancel.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Annulla")
    _add_member(db_session, league_id, bidder_id)
    athlete = _seed_athlete(db_session, 92005, "Calciatore Annullato")

    session_id = _start_manual_session(client, admin_token, league_id)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    lot_id = lot["id"]

    cancelled = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/annulla",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # Re-nominating the same athlete after cancellation is allowed.
    second_lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    raise_resp = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{second_lot['id']}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 10},
    )
    assert raise_resp.status_code == 200

    cancel_after_raise = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{second_lot['id']}/annulla",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cancel_after_raise.status_code == 400
    assert cancel_after_raise.json()["code"] == "market_live_lot_has_raises"


def test_athlete_renominated_after_pass_but_not_after_sale(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.renom.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.lot.renom.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Rinomina")
    _add_member(db_session, league_id, bidder_id)
    athlete = _seed_athlete(db_session, 92006, "Calciatore Rinominabile")

    session_id = _start_manual_session(client, admin_token, league_id)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    passed = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot['id']}/salta",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert passed.status_code == 200
    assert passed.json()["status"] == "passed"

    second_lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{second_lot['id']}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 10},
    )
    sold = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{second_lot['id']}/aggiudica",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sold.status_code == 200

    blocked = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"athleteId": str(athlete.id)},
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "athlete_already_owned"


def test_soft_close_extends_lot_window_near_expiry(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.softclose.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.lot.softclose.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Soft Close")
    _add_member(db_session, league_id, bidder_id)
    athlete = _seed_athlete(db_session, 92007, "Calciatore Soft Close")

    session_id = _start_manual_session(client, admin_token, league_id, soft_close=20)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)

    # Simulate a lot about to expire: push closes_at to 2s from now (inside the
    # 20s soft-close window), then verify a raise pushes it back out.
    near_expiry = datetime.now(UTC) + timedelta(seconds=2)
    db_row = db_session.get(MarketLiveLot, UUID(lot["id"]))
    assert db_row is not None
    db_row.closes_at = near_expiry
    db_session.commit()

    before = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert before.status_code == 200
    assert before.json()["currentLot"]["closesAt"] == near_expiry.isoformat()

    raised = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot['id']}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 10},
    )
    assert raised.status_code == 200
    new_closes_at = datetime.fromisoformat(raised.json()["closesAt"])
    assert new_closes_at > near_expiry + timedelta(seconds=10)


def test_expired_lot_auto_finalizes_on_next_poll(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.expiry.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.lot.expiry.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Scadenza")
    _add_member(db_session, league_id, bidder_id)
    athlete = _seed_athlete(db_session, 92008, "Calciatore Scaduto")

    session_id = _start_manual_session(client, admin_token, league_id)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot['id']}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 10},
    )

    db_row = db_session.get(MarketLiveLot, UUID(lot["id"]))
    assert db_row is not None
    db_row.closes_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    state = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert state.status_code == 200
    assert state.json()["currentLot"] is None

    lots = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert lots.status_code == 200
    assert lots.json()["lots"][0]["status"] == "sold"

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete.id)
    )
    assert slot is not None


def _fill_goalkeeper_quota(
    client: TestClient,
    db_session: Session,
    admin_token: str,
    bidder_token: str,
    league_id: str,
    *,
    seed_offset: int,
) -> tuple[str, list[Athlete]]:
    """Force the bidder's team to the default 3-goalkeeper quota (EP08-09 swap prompt)."""
    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {bidder_token}"})
    assert rosa.status_code == 200
    team_id = rosa.json()["id"]
    keepers = [
        _seed_athlete(db_session, seed_offset + index, f"Portiere Pieno {seed_offset}.{index}", role=FantasyRole.P)
        for index in range(3)
    ]
    for index, athlete in enumerate(keepers):
        response = client.put(
            f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{index}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"athleteId": str(athlete.id), "purchaseCredits": 1},
        )
        assert response.status_code == 200, response.json()
    return team_id, keepers


def _win_lot_against_full_quota(
    client: TestClient,
    db_session: Session,
    admin_token: str,
    bidder_token: str,
    league_id: str,
    *,
    seed_offset: int,
    amount_credits: int = 10,
) -> tuple[str, str, dict]:
    """Fill the goalkeeper quota, then win a 4th goalkeeper lot → PENDING_SWAP."""
    _fill_goalkeeper_quota(
        client, db_session, admin_token, bidder_token, league_id, seed_offset=seed_offset
    )
    extra_keeper = _seed_athlete(
        db_session, seed_offset + 900, f"Portiere Extra {seed_offset}", role=FantasyRole.P
    )
    session_id = _start_manual_session(client, admin_token, league_id)
    lot = _nominate(client, admin_token, league_id, session_id, extra_keeper.id)
    lot_id = lot["id"]
    raised = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": amount_credits},
    )
    assert raised.status_code == 200
    sold = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/aggiudica",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sold.status_code == 200
    assert sold.json()["status"] == "pending_swap"
    return session_id, lot_id, sold.json()


def test_roster_full_prompts_swap_with_same_role_candidates(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.swap.prompt.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.swap.prompt.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scambio Prompt")
    _add_member(db_session, league_id, bidder_id)

    session_id, lot_id, sold = _win_lot_against_full_quota(
        client, db_session, admin_token, bidder_token, league_id, seed_offset=93000
    )

    state = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert state.status_code == 200
    pending = state.json()["pendingSwap"]
    assert pending is not None
    assert pending["lotId"] == lot_id
    assert pending["amountCredits"] == 10
    assert pending["role"] == "P"
    assert pending["roleLabel"] == "portieri"
    assert len(pending["candidates"]) == 3
    assert all(candidate["purchaseCredits"] == 1 for candidate in pending["candidates"])

    sessions = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    assert next(row for row in sessions if row["id"] == session_id)["pendingSwapCount"] == 1

    # Not visible to a viewer who isn't the winning team: no pendingSwap leaks.
    admin_state = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_state.json()["pendingSwap"] is None


def test_resolve_swap_refunds_released_player_and_charges_new_one(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.swap.resolve.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.swap.resolve.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scambio Risolto")
    _add_member(db_session, league_id, bidder_id)

    session_id, lot_id, sold = _win_lot_against_full_quota(
        client, db_session, admin_token, bidder_token, league_id, seed_offset=93100
    )
    won_athlete_id = sold["athleteId"]

    state = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
        headers={"Authorization": f"Bearer {bidder_token}"},
    ).json()
    release_athlete_id = state["pendingSwap"]["candidates"][0]["athleteId"]

    before_balance = client.get(
        f"/leagues/{league_id}/crediti", headers={"Authorization": f"Bearer {bidder_token}"}
    ).json()["balance"]

    resolved = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/scambia",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"releaseAthleteId": release_athlete_id},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "sold"

    after_balance = client.get(
        f"/leagues/{league_id}/crediti", headers={"Authorization": f"Bearer {bidder_token}"}
    ).json()["balance"]
    # Full refund (1) for the released goalkeeper minus the winning bid (10).
    assert after_balance - before_balance == -9

    new_slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == UUID(won_athlete_id))
    )
    assert new_slot is not None
    assert new_slot.purchase_credits == 10
    released_slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == UUID(release_athlete_id))
    )
    assert released_slot is None

    state_after = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
        headers={"Authorization": f"Bearer {bidder_token}"},
    ).json()
    assert state_after["pendingSwap"] is None


def test_decline_swap_loses_lot_without_charge_and_frees_athlete(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.swap.decline.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.swap.decline.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scambio Rifiutato")
    _add_member(db_session, league_id, bidder_id)

    session_id, lot_id, sold = _win_lot_against_full_quota(
        client, db_session, admin_token, bidder_token, league_id, seed_offset=93200
    )
    won_athlete_id = sold["athleteId"]

    before_balance = client.get(
        f"/leagues/{league_id}/crediti", headers={"Authorization": f"Bearer {bidder_token}"}
    ).json()["balance"]

    declined = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rinuncia-scambio",
        headers={"Authorization": f"Bearer {bidder_token}"},
    )
    assert declined.status_code == 200
    assert declined.json()["status"] == "passed"

    after_balance = client.get(
        f"/leagues/{league_id}/crediti", headers={"Authorization": f"Bearer {bidder_token}"}
    ).json()["balance"]
    assert after_balance == before_balance

    # The declined athlete is free again and can be renominated.
    renominated = _nominate(client, admin_token, league_id, session_id, UUID(won_athlete_id))
    assert renominated["status"] == "open"


def test_swap_actions_forbidden_for_non_winning_team(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.swap.forbid.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.swap.forbid.bidder@example.com")
    other_token, other_id = _register_and_login(client, "live.swap.forbid.other@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scambio Vietato")
    _add_member(db_session, league_id, bidder_id)
    _add_member(db_session, league_id, other_id)

    session_id, lot_id, _sold = _win_lot_against_full_quota(
        client, db_session, admin_token, bidder_token, league_id, seed_offset=93300
    )

    forbidden = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rinuncia-scambio",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden.status_code == 400
    assert forbidden.json()["code"] == "market_live_swap_not_owner"


def test_end_session_auto_declines_pending_swap(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.swap.end.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.swap.end.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scambio Fine Sessione")
    _add_member(db_session, league_id, bidder_id)

    session_id, lot_id, _sold = _win_lot_against_full_quota(
        client, db_session, admin_token, bidder_token, league_id, seed_offset=93400
    )

    ended = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/termina",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "resolved"

    lots = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()
    lot = next(row for row in lots["lots"] if row["id"] == lot_id)
    assert lot["status"] == "passed"


def test_raise_allowed_with_physically_full_roster_and_prompts_swap_on_win(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """A generically full roster (all slots occupied, not just one role's quota)
    must not block a raise — only winning triggers the swap prompt (EP08-09)."""
    admin_token, _ = _register_and_login(client, "live.swap.fullroster.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.swap.fullroster.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Rosa Fisicamente Piena")
    _add_member(db_session, league_id, bidder_id)

    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {bidder_token}"})
    assert rosa.status_code == 200
    team_id = rosa.json()["id"]

    # Default quotas: 3 P, 11 D, 11 C, 10 A — exactly fills the default 35-slot roster.
    role_counts = [(FantasyRole.P, 3), (FantasyRole.D, 11), (FantasyRole.C, 11), (FantasyRole.A, 10)]
    slot_index = 0
    seed_offset = 93500
    for role, count in role_counts:
        for i in range(count):
            athlete = _seed_athlete(db_session, seed_offset, f"Roster Pieno {seed_offset}", role=role)
            seed_offset += 1
            response = client.put(
                f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"athleteId": str(athlete.id), "purchaseCredits": 1},
            )
            assert response.status_code == 200, response.json()
            slot_index += 1

    extra_forward = _seed_athlete(db_session, seed_offset + 1, "Attaccante Extra", role=FantasyRole.A)

    session_id = _start_manual_session(client, admin_token, league_id)
    lot = _nominate(client, admin_token, league_id, session_id, extra_forward.id)
    lot_id = lot["id"]

    raised = client.put(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 10},
    )
    assert raised.status_code == 200, raised.json()

    sold = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/aggiudica",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sold.status_code == 200
    assert sold.json()["status"] == "pending_swap"

    state = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato",
        headers={"Authorization": f"Bearer {bidder_token}"},
    ).json()
    assert state["pendingSwap"] is not None
    assert state["pendingSwap"]["role"] == "A"
    assert len(state["pendingSwap"]["candidates"]) == 10


def test_concurrent_raises_leave_one_leader_and_correct_amount(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.conc.admin@example.com")
    bidder_a_token, bidder_a_id = _register_and_login(client, "live.lot.conc.a@example.com")
    bidder_b_token, bidder_b_id = _register_and_login(client, "live.lot.conc.b@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Concorrenza")
    _add_member(db_session, league_id, bidder_a_id)
    _add_member(db_session, league_id, bidder_b_id)
    athlete = _seed_athlete(db_session, 92009, "Calciatore Conteso")

    session_id = _start_manual_session(client, admin_token, league_id, min_increment=10)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    lot_id = lot["id"]

    def _raise(token: str) -> int:
        response = client.put(
            f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/rilanci",
            headers={"Authorization": f"Bearer {token}"},
            json={"amountCredits": 10},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(_raise, [bidder_a_token, bidder_b_token]))

    assert sorted(statuses) == [200, 400]

    db_row = db_session.get(MarketLiveLot, UUID(lot_id))
    assert db_row is not None
    assert db_row.current_amount_credits == 10
    assert db_row.current_leader_team_id is not None
