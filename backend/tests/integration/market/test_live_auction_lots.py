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

from database.enums import FantasyRole, LeagueAuditAction, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import CreditLedgerEntry, FantasyRosterSlot
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from market.live_models import MarketLiveLot, MarketLiveRaise
from notifications.models import Notification
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


def _unique_id() -> int:
    """Identificativo calciatore mai riusato (il database di test non si svuota tra le prove)."""
    import random

    return random.randint(100_000_000, 2_000_000_000)


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
    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {bidder_token}"}
    )
    assert rosa.status_code == 200
    team_id = rosa.json()["id"]
    keepers = [
        _seed_athlete(
            db_session,
            seed_offset + index,
            f"Portiere Pieno {seed_offset}.{index}",
            role=FantasyRole.P,
        )
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
    # Rimborso del 50% (percentuale di lega, per difetto) di 1 credito = 0, meno l'offerta (10).
    assert after_balance - before_balance == -10

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

    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {bidder_token}"}
    )
    assert rosa.status_code == 200
    team_id = rosa.json()["id"]

    # Default quotas: 3 P, 11 D, 11 C, 10 A — exactly fills the default 35-slot roster.
    role_counts = [
        (FantasyRole.P, 3),
        (FantasyRole.D, 11),
        (FantasyRole.C, 11),
        (FantasyRole.A, 10),
    ]
    slot_index = 0
    seed_offset = 93500
    for role, count in role_counts:
        for i in range(count):
            athlete = _seed_athlete(
                db_session, seed_offset, f"Roster Pieno {seed_offset}", role=role
            )
            seed_offset += 1
            response = client.put(
                f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"athleteId": str(athlete.id), "purchaseCredits": 1},
            )
            assert response.status_code == 200, response.json()
            slot_index += 1

    extra_forward = _seed_athlete(
        db_session, seed_offset + 1, "Attaccante Extra", role=FantasyRole.A
    )

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


def test_pass_and_cancel_lot_blocked_when_market_closed(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.closed.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.lot.closed.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Mercato Chiuso")
    _add_member(db_session, league_id, bidder_id)
    athlete = _seed_athlete(db_session, 92501, "Calciatore Mercato Chiuso")
    base = f"/leagues/{league_id}/mercato/asta-live/sessioni"

    session_id = _start_manual_session(client, admin_token, league_id)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    headers = {"Authorization": f"Bearer {admin_token}"}
    assert (
        client.put(
            f"{base}/{session_id}/lotti/{lot['id']}/rilanci",
            headers={"Authorization": f"Bearer {bidder_token}"},
            json={"amountCredits": 10},
        ).status_code
        == 200
    )
    client.post(f"/leagues/{league_id}/mercato/stato", headers=headers, json={"open": False})

    for action in ("salta", "annulla"):
        blocked = client.post(f"{base}/{session_id}/lotti/{lot['id']}/{action}", headers=headers)
        assert blocked.status_code == 400, action
        assert blocked.json()["code"] == "market_closed", action

    client.post(f"/leagues/{league_id}/mercato/stato", headers=headers, json={"open": True})
    passed = client.post(f"{base}/{session_id}/lotti/{lot['id']}/salta", headers=headers)
    assert passed.status_code == 200


def test_live_nomination_rejected_for_athlete_without_valid_role(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.norole.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Lotti Senza Ruolo")
    no_role = Athlete(provider_id=92510, canonical_name="Calciatore Senza Ruolo")
    db_session.add(no_role)
    db_session.commit()
    db_session.refresh(no_role)

    session_id = _start_manual_session(client, admin_token, league_id)
    response = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/nomina",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"athleteId": str(no_role.id)},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "role_unresolved"


def test_resolve_swap_blocked_when_market_closed_and_reports_specific_errors(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.swap.closed.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.swap.closed.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Scambio Chiuso")
    _add_member(db_session, league_id, bidder_id)
    session_id, lot_id, _ = _win_lot_against_full_quota(
        client, db_session, admin_token, bidder_token, league_id, seed_offset=_unique_id()
    )
    url = f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/lotti/{lot_id}/scambia"
    bidder = {"Authorization": f"Bearer {bidder_token}"}
    admin = {"Authorization": f"Bearer {admin_token}"}
    state = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato", headers=bidder
    ).json()
    keeper_id = state["pendingSwap"]["candidates"][0]["athleteId"]

    client.post(f"/leagues/{league_id}/mercato/stato", headers=admin, json={"open": False})
    blocked = client.post(url, headers=bidder, json={"releaseAthleteId": keeper_id})
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "market_closed"
    client.post(f"/leagues/{league_id}/mercato/stato", headers=admin, json={"open": True})

    stranger = _seed_athlete(db_session, _unique_id(), "Fuori Rosa", role=FantasyRole.P)
    not_mine = client.post(url, headers=bidder, json={"releaseAthleteId": str(stranger.id)})
    assert not_mine.status_code == 400
    assert not_mine.json()["code"] == "market_live_swap_athlete_not_in_roster"


def test_expired_live_window_rejects_nomination_and_raise(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "live.lot.window.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.lot.window.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Finestra Scaduta")
    _add_member(db_session, league_id, bidder_id)
    first = _seed_athlete(db_session, _unique_id(), "Finestra Uno")
    second = _seed_athlete(db_session, _unique_id(), "Finestra Due")
    session_id = _start_manual_session(client, admin_token, league_id)
    lot = _nominate(client, admin_token, league_id, session_id, first.id)

    from market.models import MarketSession

    market_session = db_session.get(MarketSession, UUID(session_id))
    market_session.opens_at = datetime.now(UTC) - timedelta(minutes=5)
    market_session.closes_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    base = f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}"
    # Tolleranza: il lotto già aperto alla fine della sessione si può ancora rilanciare.
    raised = client.put(
        f"{base}/lotti/{lot['id']}/rilanci",
        headers={"Authorization": f"Bearer {bidder_token}"},
        json={"amountCredits": 10},
    )
    assert raised.status_code == 200, raised.text
    # ...ma non si apre un nuovo lotto, né una seconda sessione mentre quello è aperto.
    second_session = client.post(
        f"/leagues/{league_id}/mercato/asta-live/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": datetime.now(UTC).isoformat(),
            "closesAt": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "nominationMode": "manual",
            "minIncrementCredits": 10,
            "softCloseSeconds": 5,
            "lotDurationSeconds": 30,
        },
    )
    assert second_session.status_code == 400
    assert second_session.json()["code"] == "market_session_already_active"
    nominated = client.post(
        f"{base}/lotti/nomina",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"athleteId": str(second.id)},
    )
    assert nominated.status_code == 400
    assert nominated.json()["code"] == "market_live_session_not_open"


def test_closing_the_market_pauses_the_live_lot_timer(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """QA 18/11: a mercato chiuso il timer del lotto si ferma e riparte alla riapertura."""
    from market.live_models import MarketLiveLot

    admin_token, _ = _register_and_login(client, "live.pause.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Pausa Lotto")
    athlete = _seed_athlete(db_session, _unique_id(), "Calciatore In Pausa")
    session_id = _start_manual_session(client, admin_token, league_id, lot_duration=30)
    lot = _nominate(client, admin_token, league_id, session_id, athlete.id)
    headers = {"Authorization": f"Bearer {admin_token}"}

    client.post(f"/leagues/{league_id}/mercato/stato", headers=headers, json={"open": False})
    db_session.expire_all()
    row = db_session.get(MarketLiveLot, UUID(lot["id"]))
    assert row is not None and row.paused_at is not None
    original_close = row.closes_at

    # Simula 5 minuti di mercato chiuso: alla riapertura la scadenza slitta di altrettanto.
    row.paused_at = row.paused_at - timedelta(minutes=5)
    db_session.commit()
    client.post(f"/leagues/{league_id}/mercato/stato", headers=headers, json={"open": True})
    db_session.expire_all()
    resumed = db_session.get(MarketLiveLot, UUID(lot["id"]))
    assert resumed.paused_at is None
    assert resumed.closes_at >= original_close + timedelta(minutes=5)
    state = client.get(
        f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}/stato", headers=headers
    ).json()
    assert state["currentLot"]["status"] == "open"


# -- P4 (QA 19/11): capofila che alla chiusura non può pagare -> offerta successiva ---------


def _live_base(league_id: str, session_id: str) -> str:
    return f"/leagues/{league_id}/mercato/asta-live/sessioni/{session_id}"


def _place_raise(
    client: TestClient, token: str, league_id: str, session_id: str, lot_id: str, amount: int
) -> None:
    response = client.put(
        f"{_live_base(league_id, session_id)}/lotti/{lot_id}/rilanci",
        headers={"Authorization": f"Bearer {token}"},
        json={"amountCredits": amount},
    )
    assert response.status_code == 200, response.json()


def _my_team(client: TestClient, token: str, league_id: str) -> dict:
    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    assert rosa.status_code == 200
    return rosa.json()


def _admin_adjust_credits(
    client: TestClient,
    admin_token: str,
    league_id: str,
    team_id: str,
    amount: int,
    transaction_id: str,
) -> None:
    response = client.post(
        f"/leagues/{league_id}/amministrazione/crediti/movimenti",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "fantasyTeamId": team_id,
            "amount": amount,
            "transactionId": transaction_id,
            "note": "Correzione di prova",
        },
    )
    assert response.status_code == 200, response.json()


def _balance(client: TestClient, token: str, league_id: str) -> int:
    response = client.get(
        f"/leagues/{league_id}/crediti", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    return response.json()["balance"]


def _expire_and_poll(
    client: TestClient,
    db_session: Session,
    token: str,
    league_id: str,
    session_id: str,
    lot_id: str,
) -> dict:
    """Fa scadere il lotto e lascia che lo chiuda la prima lettura (chiusura automatica)."""
    row = db_session.get(MarketLiveLot, UUID(lot_id))
    assert row is not None
    row.closes_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    headers = {"Authorization": f"Bearer {token}"}
    state = client.get(f"{_live_base(league_id, session_id)}/stato", headers=headers)
    assert state.status_code == 200
    assert state.json()["currentLot"] is None
    lots = client.get(f"{_live_base(league_id, session_id)}/lotti", headers=headers)
    assert lots.status_code == 200
    db_session.expire_all()
    return next(row for row in lots.json()["lots"] if row["id"] == lot_id)


def _notifications(db_session: Session, user_id: UUID, template_key: str) -> list[Notification]:
    return list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == user_id,
                Notification.template_key == template_key,
            )
        ).all()
    )


def _win_ledger_entries(db_session: Session, lot_id: str) -> list[CreditLedgerEntry]:
    """Addebiti dell'aggiudicazione di questo lotto, su qualunque squadra."""
    return list(
        db_session.scalars(
            select(CreditLedgerEntry).where(
                CreditLedgerEntry.transaction_id.like(f"market-live:{lot_id}:%")
            )
        ).all()
    )


def _lot_audit(
    db_session: Session, lot_id: str, action: LeagueAuditAction
) -> list[LeagueAuditEvent]:
    rows = db_session.scalars(
        select(LeagueAuditEvent).where(LeagueAuditEvent.action == action)
    ).all()
    return [row for row in rows if (row.details or {}).get("lotId") == lot_id]


def test_expired_lot_goes_to_runner_up_when_leader_lacks_credits(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """P4: 100 di qa-02, 500 di qa-04, l'amministratore toglie crediti a qa-04, il lotto
    scade. Il calciatore va a qa-02 a 100, con un solo addebito, ed entrambi vengono avvisati."""
    admin_token, _ = _register_and_login(client, "live.p4.admin@example.com")
    second_token, second_id = _register_and_login(client, "live.p4.second@example.com")
    leader_token, leader_id = _register_and_login(client, "live.p4.leader@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega P4 Seconda Offerta")
    _add_member(db_session, league_id, second_id)
    _add_member(db_session, league_id, leader_id)
    athlete = _seed_athlete(db_session, _unique_id(), "Calciatore P4")
    session_id = _start_manual_session(client, admin_token, league_id)
    lot_id = _nominate(client, admin_token, league_id, session_id, athlete.id)["id"]

    _place_raise(client, second_token, league_id, session_id, lot_id, 100)
    _place_raise(client, leader_token, league_id, session_id, lot_id, 500)
    second_team = _my_team(client, second_token, league_id)
    leader_team = _my_team(client, leader_token, league_id)
    _admin_adjust_credits(client, admin_token, league_id, leader_team["id"], -600, "p4-addebito")
    assert _balance(client, leader_token, league_id) == 400

    lot = _expire_and_poll(client, db_session, admin_token, league_id, session_id, lot_id)
    assert lot["status"] == "sold"
    assert lot["currentLeaderTeamId"] == second_team["id"]
    assert lot["currentLeaderTeamName"] == second_team["name"]
    assert lot["currentAmountCredits"] == 100

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete.id)
    )
    assert slot is not None
    assert str(slot.fantasy_team_id) == second_team["id"]
    assert slot.purchase_credits == 100

    # Un solo addebito, al vincitore effettivo e al prezzo della sua offerta.
    assert _balance(client, second_token, league_id) == 900
    assert _balance(client, leader_token, league_id) == 400
    assert [entry.amount for entry in _win_ledger_entries(db_session, lot_id)] == [-100]

    won = _notifications(db_session, second_id, "mercato.asta_live_aggiudicato")
    assert len(won) == 1
    assert won[0].title == "Lotto aggiudicato"
    assert "100 crediti" in won[0].body
    lost = _notifications(db_session, leader_id, "mercato.asta_live_perso")
    assert len(lost) == 1
    assert lost[0].title == "Lotto perso: crediti insufficienti"
    assert "Calciatore P4" in lost[0].body
    assert lost[0].deep_link == f"/asta-live?lega={league_id}"
    assert _notifications(db_session, leader_id, "mercato.asta_live_aggiudicato") == []

    sold_events = _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SOLD)
    assert len(sold_events) == 1
    assert sold_events[0].actor_id is None  # chiusura automatica, non un'azione di chi legge
    details = sold_events[0].details
    assert details["fantasyTeamId"] == second_team["id"]
    assert details["amountCredits"] == 100
    assert details["formerLeaderTeamId"] == leader_team["id"]
    assert details["formerAmountCredits"] == 500
    assert details["reason"] == "insufficient_credits"
    assert _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_PASSED) == []


def test_runner_up_tie_goes_to_the_earliest_bid(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Due offerte successive allo stesso importo: vince chi ha offerto prima."""
    admin_token, _ = _register_and_login(client, "live.p4.tie.admin@example.com")
    later_token, later_id = _register_and_login(client, "live.p4.tie.later@example.com")
    earlier_token, earlier_id = _register_and_login(client, "live.p4.tie.earlier@example.com")
    leader_token, leader_id = _register_and_login(client, "live.p4.tie.leader@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega P4 Parità")
    for user_id in (later_id, earlier_id, leader_id):
        _add_member(db_session, league_id, user_id)
    athlete = _seed_athlete(db_session, _unique_id(), "Calciatore Parità")
    session_id = _start_manual_session(client, admin_token, league_id)
    lot_id = _nominate(client, admin_token, league_id, session_id, athlete.id)["id"]

    later_team = _my_team(client, later_token, league_id)
    earlier_team = _my_team(client, earlier_token, league_id)
    leader_team = _my_team(client, leader_token, league_id)
    _place_raise(client, later_token, league_id, session_id, lot_id, 10)
    _place_raise(client, leader_token, league_id, session_id, lot_id, 20)
    # A rilanci non si arriva a due offerte uguali: la seconda si inserisce a mano,
    # registrata dopo ma datata prima, così l'ordine di inserimento non decide nulla.
    later_raise = db_session.scalar(
        select(MarketLiveRaise).where(
            MarketLiveRaise.lot_id == UUID(lot_id),
            MarketLiveRaise.fantasy_team_id == UUID(later_team["id"]),
        )
    )
    assert later_raise is not None
    db_session.add(
        MarketLiveRaise(
            lot_id=UUID(lot_id),
            fantasy_team_id=UUID(earlier_team["id"]),
            amount_credits=10,
            placed_at=later_raise.placed_at - timedelta(seconds=5),
        )
    )
    db_session.commit()
    _admin_adjust_credits(client, admin_token, league_id, leader_team["id"], -995, "p4-pari")

    lot = _expire_and_poll(client, db_session, admin_token, league_id, session_id, lot_id)
    assert lot["status"] == "sold"
    assert lot["currentLeaderTeamId"] == earlier_team["id"]
    assert lot["currentAmountCredits"] == 10

    slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete.id)
    )
    assert slot is not None
    assert str(slot.fantasy_team_id) == earlier_team["id"]
    assert _balance(client, earlier_token, league_id) == 990
    assert _balance(client, later_token, league_id) == 1000
    assert _balance(client, leader_token, league_id) == 5
    assert [entry.amount for entry in _win_ledger_entries(db_session, lot_id)] == [-10]
    assert len(_notifications(db_session, earlier_id, "mercato.asta_live_aggiudicato")) == 1
    assert _notifications(db_session, later_id, "mercato.asta_live_aggiudicato") == []
    assert len(_notifications(db_session, leader_id, "mercato.asta_live_perso")) == 1


def test_lot_passes_when_no_runner_up_can_be_assigned(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Nessuna offerta successiva valida (una senza crediti, una senza posto): il lotto passa."""
    admin_token, _ = _register_and_login(client, "live.p4.none.admin@example.com")
    poor_token, poor_id = _register_and_login(client, "live.p4.none.poor@example.com")
    full_token, full_id = _register_and_login(client, "live.p4.none.full@example.com")
    leader_token, leader_id = _register_and_login(client, "live.p4.none.leader@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega P4 Nessuno")
    for user_id in (poor_id, full_id, leader_id):
        _add_member(db_session, league_id, user_id)
    # Chi ha i crediti ha già tre portieri: il quarto non entra (e da seconda offerta
    # non si propone lo scambio, serve un posto libero).
    _fill_goalkeeper_quota(
        client, db_session, admin_token, full_token, league_id, seed_offset=_unique_id()
    )
    keeper = _seed_athlete(db_session, _unique_id(), "Portiere Conteso", role=FantasyRole.P)
    session_id = _start_manual_session(client, admin_token, league_id)
    lot_id = _nominate(client, admin_token, league_id, session_id, keeper.id)["id"]

    poor_team = _my_team(client, poor_token, league_id)
    leader_team = _my_team(client, leader_token, league_id)
    _place_raise(client, poor_token, league_id, session_id, lot_id, 10)
    _place_raise(client, full_token, league_id, session_id, lot_id, 20)
    _place_raise(client, leader_token, league_id, session_id, lot_id, 30)
    _admin_adjust_credits(client, admin_token, league_id, poor_team["id"], -995, "p4-poor")
    _admin_adjust_credits(client, admin_token, league_id, leader_team["id"], -990, "p4-leader")
    balances_before = {
        token: _balance(client, token, league_id)
        for token in (poor_token, full_token, leader_token)
    }

    lot = _expire_and_poll(client, db_session, admin_token, league_id, session_id, lot_id)
    assert lot["status"] == "passed"
    assert (
        db_session.scalar(
            select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == keeper.id)
        )
        is None
    )
    assert {
        token: _balance(client, token, league_id) for token in balances_before
    } == balances_before
    assert _win_ledger_entries(db_session, lot_id) == []
    for user_id in (poor_id, full_id, leader_id):
        assert _notifications(db_session, user_id, "mercato.asta_live_aggiudicato") == []
        assert _notifications(db_session, user_id, "mercato.asta_live_scambio_richiesto") == []
    lost = _notifications(db_session, leader_id, "mercato.asta_live_perso")
    assert len(lost) == 1
    assert lost[0].title == "Lotto perso: crediti insufficienti"
    assert "svincolato" in lost[0].body

    passed_events = _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_PASSED)
    assert len(passed_events) == 1
    assert passed_events[0].actor_id is None  # chiusura automatica
    assert passed_events[0].details["reason"] == "insufficient_credits"
    assert _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SOLD) == []


def test_expired_lot_with_solvent_leader_is_sold_as_before(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Caso normale invariato: vince il capofila al suo prezzo, nessuno riceve «lotto perso»."""
    admin_token, admin_id = _register_and_login(client, "live.p4.ok.admin@example.com")
    second_token, second_id = _register_and_login(client, "live.p4.ok.second@example.com")
    leader_token, leader_id = _register_and_login(client, "live.p4.ok.leader@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega P4 Normale")
    _add_member(db_session, league_id, second_id)
    _add_member(db_session, league_id, leader_id)
    athlete = _seed_athlete(db_session, _unique_id(), "Calciatore Normale")
    session_id = _start_manual_session(client, admin_token, league_id)
    lot_id = _nominate(client, admin_token, league_id, session_id, athlete.id)["id"]

    _place_raise(client, second_token, league_id, session_id, lot_id, 10)
    _place_raise(client, leader_token, league_id, session_id, lot_id, 20)
    leader_team = _my_team(client, leader_token, league_id)

    lot = _expire_and_poll(client, db_session, admin_token, league_id, session_id, lot_id)
    assert lot["status"] == "sold"
    assert lot["currentLeaderTeamId"] == leader_team["id"]
    assert lot["currentAmountCredits"] == 20
    assert _balance(client, leader_token, league_id) == 980
    assert _balance(client, second_token, league_id) == 1000
    assert [entry.amount for entry in _win_ledger_entries(db_session, lot_id)] == [-20]
    assert len(_notifications(db_session, leader_id, "mercato.asta_live_aggiudicato")) == 1
    for user_id in (second_id, leader_id):
        assert _notifications(db_session, user_id, "mercato.asta_live_perso") == []

    sold_events = _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SOLD)
    assert len(sold_events) == 1
    assert sold_events[0].actor_id is None  # chiusura automatica, non un'azione di chi legge
    assert sold_events[0].details == {
        "lotId": lot_id,
        "athleteId": str(athlete.id),
        "fantasyTeamId": leader_team["id"],
        "amountCredits": 20,
    }


def test_force_sell_falls_back_to_runner_up_with_admin_as_actor(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """«Aggiudica» dell'amministratore: stessa regola, e nel registro l'autore è lui."""
    admin_token, admin_id = _register_and_login(client, "live.p4.force.admin@example.com")
    second_token, second_id = _register_and_login(client, "live.p4.force.second@example.com")
    leader_token, leader_id = _register_and_login(client, "live.p4.force.leader@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega P4 Aggiudica")
    _add_member(db_session, league_id, second_id)
    _add_member(db_session, league_id, leader_id)
    athlete = _seed_athlete(db_session, _unique_id(), "Calciatore Aggiudicato")
    session_id = _start_manual_session(client, admin_token, league_id)
    lot_id = _nominate(client, admin_token, league_id, session_id, athlete.id)["id"]

    _place_raise(client, second_token, league_id, session_id, lot_id, 10)
    _place_raise(client, leader_token, league_id, session_id, lot_id, 20)
    second_team = _my_team(client, second_token, league_id)
    leader_team = _my_team(client, leader_token, league_id)
    _admin_adjust_credits(client, admin_token, league_id, leader_team["id"], -995, "p4-force")

    sold = client.post(
        f"{_live_base(league_id, session_id)}/lotti/{lot_id}/aggiudica",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sold.status_code == 200
    body = sold.json()
    assert body["status"] == "sold"
    assert body["currentLeaderTeamId"] == second_team["id"]
    assert body["currentLeaderTeamName"] == second_team["name"]
    assert body["currentAmountCredits"] == 10
    assert _balance(client, second_token, league_id) == 990
    assert _balance(client, leader_token, league_id) == 5

    db_session.expire_all()
    sold_events = _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SOLD)
    assert len(sold_events) == 1
    assert sold_events[0].actor_id == admin_id
    assert sold_events[0].details["formerLeaderTeamId"] == leader_team["id"]
    assert len(_notifications(db_session, leader_id, "mercato.asta_live_perso")) == 1


# -- Autore nel registro: chiusura automatica (nessuno) e manuale (l'amministratore) -----------


def test_automatic_lot_close_has_no_actor_in_the_audit(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Il lotto scade e lo chiude la lettura dello stato di un partecipante qualunque:
    né il «passato» né il «venduto» (né l'addebito) vanno attribuiti a chi ha letto."""
    admin_token, admin_id = _register_and_login(client, "live.actor.auto.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.actor.auto.bidder@example.com")
    viewer_token, viewer_id = _register_and_login(client, "live.actor.auto.viewer@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Autore Automatico")
    _add_member(db_session, league_id, bidder_id)
    _add_member(db_session, league_id, viewer_id)
    unsold = _seed_athlete(db_session, _unique_id(), "Calciatore Senza Offerte")
    sold = _seed_athlete(db_session, _unique_id(), "Calciatore Venduto Da Solo")
    session_id = _start_manual_session(client, admin_token, league_id)

    passed_lot_id = _nominate(client, admin_token, league_id, session_id, unsold.id)["id"]
    lot = _expire_and_poll(client, db_session, viewer_token, league_id, session_id, passed_lot_id)
    assert lot["status"] == "passed"
    passed_events = _lot_audit(db_session, passed_lot_id, LeagueAuditAction.MARKET_LIVE_LOT_PASSED)
    assert len(passed_events) == 1
    assert passed_events[0].actor_id is None

    sold_lot_id = _nominate(client, admin_token, league_id, session_id, sold.id)["id"]
    _place_raise(client, bidder_token, league_id, session_id, sold_lot_id, 30)
    lot = _expire_and_poll(client, db_session, viewer_token, league_id, session_id, sold_lot_id)
    assert lot["status"] == "sold"
    sold_events = _lot_audit(db_session, sold_lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SOLD)
    assert len(sold_events) == 1
    assert sold_events[0].actor_id is None
    assert [
        (entry.amount, entry.actor_id) for entry in _win_ledger_entries(db_session, sold_lot_id)
    ] == [(-30, None)]
    assert _balance(client, bidder_token, league_id) == 970


def test_manual_pass_and_sell_keep_the_admin_as_actor(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """«Salta» e «Aggiudica» sono decisioni dell'amministratore: nel registro l'autore è lui."""
    admin_token, admin_id = _register_and_login(client, "live.actor.manual.admin@example.com")
    bidder_token, bidder_id = _register_and_login(client, "live.actor.manual.bidder@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Autore Manuale")
    _add_member(db_session, league_id, bidder_id)
    skipped = _seed_athlete(db_session, _unique_id(), "Calciatore Saltato")
    sold = _seed_athlete(db_session, _unique_id(), "Calciatore Aggiudicato A Mano")
    session_id = _start_manual_session(client, admin_token, league_id)
    admin = {"Authorization": f"Bearer {admin_token}"}

    skipped_lot_id = _nominate(client, admin_token, league_id, session_id, skipped.id)["id"]
    _place_raise(client, bidder_token, league_id, session_id, skipped_lot_id, 10)
    response = client.post(
        f"{_live_base(league_id, session_id)}/lotti/{skipped_lot_id}/salta", headers=admin
    )
    assert response.status_code == 200
    assert response.json()["status"] == "passed"

    sold_lot_id = _nominate(client, admin_token, league_id, session_id, sold.id)["id"]
    _place_raise(client, bidder_token, league_id, session_id, sold_lot_id, 20)
    response = client.post(
        f"{_live_base(league_id, session_id)}/lotti/{sold_lot_id}/aggiudica", headers=admin
    )
    assert response.status_code == 200
    assert response.json()["status"] == "sold"

    db_session.expire_all()
    passed_events = _lot_audit(db_session, skipped_lot_id, LeagueAuditAction.MARKET_LIVE_LOT_PASSED)
    assert [event.actor_id for event in passed_events] == [admin_id]
    sold_events = _lot_audit(db_session, sold_lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SOLD)
    assert [event.actor_id for event in sold_events] == [admin_id]
    assert [
        (entry.amount, entry.actor_id) for entry in _win_ledger_entries(db_session, sold_lot_id)
    ] == [(-20, admin_id)]


# -- Capofila a rosa piena che non sceglie lo scambio: il lotto va all'offerta successiva ------


def _pending_swap_lot(
    client: TestClient,
    db_session: Session,
    admin_token: str,
    league_id: str,
    leader_token: str,
    raises: list[tuple[str, int]],
    *,
    name: str,
) -> tuple[str, str]:
    """Capofila con i portieri al completo che vince un portiere: lotto in attesa di scambio.

    ``raises`` sono i rilanci in ordine (token, importo); l'ultimo deve essere del capofila.
    """
    _fill_goalkeeper_quota(
        client, db_session, admin_token, leader_token, league_id, seed_offset=_unique_id()
    )
    keeper = _seed_athlete(db_session, _unique_id(), name, role=FantasyRole.P)
    session_id = _start_manual_session(client, admin_token, league_id)
    lot_id = _nominate(client, admin_token, league_id, session_id, keeper.id)["id"]
    for token, amount in raises:
        _place_raise(client, token, league_id, session_id, lot_id, amount)
    sold = client.post(
        f"{_live_base(league_id, session_id)}/lotti/{lot_id}/aggiudica",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert sold.status_code == 200
    assert sold.json()["status"] == "pending_swap"
    return session_id, lot_id


def _lot_athlete_owner(db_session: Session, lot_id: str) -> FantasyRosterSlot | None:
    db_session.expire_all()
    lot = db_session.get(MarketLiveLot, UUID(lot_id))
    assert lot is not None
    return db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == lot.athlete_id)
    )


def test_declined_swap_gives_the_lot_to_the_next_bid(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Il capofila a rosa piena rinuncia allo scambio: il portiere va alla seconda offerta,
    che paga la propria offerta una sola volta; il capofila riceve «rosa al completo»."""
    admin_token, _ = _register_and_login(client, "live.swapfb.decline.admin@example.com")
    runner_token, runner_id = _register_and_login(client, "live.swapfb.decline.runner@example.com")
    leader_token, leader_id = _register_and_login(client, "live.swapfb.decline.leader@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Rinuncia Scambio P4")
    _add_member(db_session, league_id, runner_id)
    _add_member(db_session, league_id, leader_id)
    session_id, lot_id = _pending_swap_lot(
        client,
        db_session,
        admin_token,
        league_id,
        leader_token,
        [(runner_token, 10), (leader_token, 20)],
        name="Portiere Rinunciato",
    )
    runner_team = _my_team(client, runner_token, league_id)
    leader_team = _my_team(client, leader_token, league_id)
    leader_before = _balance(client, leader_token, league_id)

    declined = client.post(
        f"{_live_base(league_id, session_id)}/lotti/{lot_id}/rinuncia-scambio",
        headers={"Authorization": f"Bearer {leader_token}"},
    )
    assert declined.status_code == 200, declined.json()
    body = declined.json()
    assert body["status"] == "sold"
    assert body["currentLeaderTeamId"] == runner_team["id"]
    assert body["currentLeaderTeamName"] == runner_team["name"]
    assert body["currentAmountCredits"] == 10

    slot = _lot_athlete_owner(db_session, lot_id)
    assert slot is not None
    assert str(slot.fantasy_team_id) == runner_team["id"]
    assert slot.purchase_credits == 10
    assert _balance(client, runner_token, league_id) == 990
    assert _balance(client, leader_token, league_id) == leader_before
    assert [entry.amount for entry in _win_ledger_entries(db_session, lot_id)] == [-10]

    assert len(_notifications(db_session, runner_id, "mercato.asta_live_aggiudicato")) == 1
    assert _notifications(db_session, leader_id, "mercato.asta_live_aggiudicato") == []
    lost = _notifications(db_session, leader_id, "mercato.asta_live_perso")
    assert len(lost) == 1
    assert lost[0].title == "Lotto perso: rosa al completo"
    assert "Portiere Rinunciato" in lost[0].body
    assert "offerta successiva" in lost[0].body

    declined_events = _lot_audit(
        db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SWAP_DECLINED
    )
    assert [event.actor_id for event in declined_events] == [leader_id]
    sold_events = _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SOLD)
    assert len(sold_events) == 1
    assert sold_events[0].actor_id == leader_id
    assert sold_events[0].details["fantasyTeamId"] == runner_team["id"]
    assert sold_events[0].details["amountCredits"] == 10
    assert sold_events[0].details["formerLeaderTeamId"] == leader_team["id"]
    assert sold_events[0].details["formerAmountCredits"] == 20
    assert sold_events[0].details["reason"] == "swap_declined"
    assert _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_PASSED) == []


def test_swap_still_pending_at_session_end_goes_to_the_earliest_next_bid(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Scambio ancora da scegliere quando l'amministratore termina la sessione: il lotto va
    all'offerta successiva; a parità vince chi ha offerto prima."""
    admin_token, admin_id = _register_and_login(client, "live.swapfb.end.admin@example.com")
    later_token, later_id = _register_and_login(client, "live.swapfb.end.later@example.com")
    earlier_token, earlier_id = _register_and_login(client, "live.swapfb.end.earlier@example.com")
    leader_token, leader_id = _register_and_login(client, "live.swapfb.end.leader@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Fine Sessione P4")
    for user_id in (later_id, earlier_id, leader_id):
        _add_member(db_session, league_id, user_id)
    _fill_goalkeeper_quota(
        client, db_session, admin_token, leader_token, league_id, seed_offset=_unique_id()
    )
    keeper = _seed_athlete(db_session, _unique_id(), "Portiere In Sospeso", role=FantasyRole.P)
    session_id = _start_manual_session(client, admin_token, league_id)
    lot_id = _nominate(client, admin_token, league_id, session_id, keeper.id)["id"]
    later_team = _my_team(client, later_token, league_id)
    earlier_team = _my_team(client, earlier_token, league_id)
    leader_team = _my_team(client, leader_token, league_id)
    _place_raise(client, later_token, league_id, session_id, lot_id, 10)
    _place_raise(client, leader_token, league_id, session_id, lot_id, 20)
    # Seconda offerta allo stesso importo, registrata dopo ma datata prima (come nel caso P4).
    later_raise = db_session.scalar(
        select(MarketLiveRaise).where(
            MarketLiveRaise.lot_id == UUID(lot_id),
            MarketLiveRaise.fantasy_team_id == UUID(later_team["id"]),
        )
    )
    assert later_raise is not None
    db_session.add(
        MarketLiveRaise(
            lot_id=UUID(lot_id),
            fantasy_team_id=UUID(earlier_team["id"]),
            amount_credits=10,
            placed_at=later_raise.placed_at - timedelta(seconds=5),
        )
    )
    db_session.commit()

    # Il lotto scade da sé: lo scambio viene proposto senza autore nel registro.
    lot = _expire_and_poll(client, db_session, admin_token, league_id, session_id, lot_id)
    assert lot["status"] == "pending_swap"
    pending_events = _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SWAP_PENDING)
    assert [event.actor_id for event in pending_events] == [None]

    ended = client.post(
        f"{_live_base(league_id, session_id)}/termina",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ended.status_code == 200, ended.json()
    assert ended.json()["status"] == "resolved"
    lots = client.get(
        f"{_live_base(league_id, session_id)}/lotti",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["lots"]
    lot = next(row for row in lots if row["id"] == lot_id)
    assert lot["status"] == "sold"
    assert lot["currentLeaderTeamId"] == earlier_team["id"]
    assert lot["currentAmountCredits"] == 10

    slot = _lot_athlete_owner(db_session, lot_id)
    assert slot is not None
    assert str(slot.fantasy_team_id) == earlier_team["id"]
    assert _balance(client, earlier_token, league_id) == 990
    assert _balance(client, later_token, league_id) == 1000
    assert [entry.amount for entry in _win_ledger_entries(db_session, lot_id)] == [-10]
    assert len(_notifications(db_session, earlier_id, "mercato.asta_live_aggiudicato")) == 1
    assert _notifications(db_session, later_id, "mercato.asta_live_aggiudicato") == []
    lost = _notifications(db_session, leader_id, "mercato.asta_live_perso")
    assert len(lost) == 1
    assert lost[0].title == "Lotto perso: rosa al completo"
    assert "offerta successiva" in lost[0].body

    declined_events = _lot_audit(
        db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SWAP_DECLINED
    )
    assert len(declined_events) == 1
    assert declined_events[0].actor_id == admin_id
    assert declined_events[0].details["reason"] == "session_ended"
    sold_events = _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SOLD)
    assert len(sold_events) == 1
    assert sold_events[0].actor_id == admin_id
    assert sold_events[0].details["fantasyTeamId"] == earlier_team["id"]
    assert sold_events[0].details["formerLeaderTeamId"] == leader_team["id"]
    assert sold_events[0].details["reason"] == "session_ended"


def test_declined_swap_passes_the_lot_when_no_next_bid_qualifies(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """L'unica altra offerta non ha più i crediti: il lotto passa e nessuno paga nulla."""
    admin_token, _ = _register_and_login(client, "live.swapfb.none.admin@example.com")
    poor_token, poor_id = _register_and_login(client, "live.swapfb.none.poor@example.com")
    leader_token, leader_id = _register_and_login(client, "live.swapfb.none.leader@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Rinuncia Nessuno")
    _add_member(db_session, league_id, poor_id)
    _add_member(db_session, league_id, leader_id)
    session_id, lot_id = _pending_swap_lot(
        client,
        db_session,
        admin_token,
        league_id,
        leader_token,
        [(poor_token, 10), (leader_token, 20)],
        name="Portiere Senza Acquirenti",
    )
    poor_team = _my_team(client, poor_token, league_id)
    _admin_adjust_credits(client, admin_token, league_id, poor_team["id"], -995, "swapfb-poor")
    balances_before = {
        token: _balance(client, token, league_id) for token in (poor_token, leader_token)
    }

    declined = client.post(
        f"{_live_base(league_id, session_id)}/lotti/{lot_id}/rinuncia-scambio",
        headers={"Authorization": f"Bearer {leader_token}"},
    )
    assert declined.status_code == 200, declined.json()
    assert declined.json()["status"] == "passed"

    assert _lot_athlete_owner(db_session, lot_id) is None
    assert {
        token: _balance(client, token, league_id) for token in balances_before
    } == balances_before
    assert _win_ledger_entries(db_session, lot_id) == []
    assert _notifications(db_session, poor_id, "mercato.asta_live_aggiudicato") == []
    lost = _notifications(db_session, leader_id, "mercato.asta_live_perso")
    assert len(lost) == 1
    assert lost[0].title == "Lotto perso: rosa al completo"
    assert "svincolato" in lost[0].body
    passed_events = _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_PASSED)
    assert len(passed_events) == 1
    assert passed_events[0].actor_id == leader_id
    assert passed_events[0].details["reason"] == "swap_declined"
    assert _lot_audit(db_session, lot_id, LeagueAuditAction.MARKET_LIVE_LOT_SOLD) == []

    # Il calciatore è di nuovo libero: si può richiamare.
    db_session.expire_all()
    keeper_id = db_session.get(MarketLiveLot, UUID(lot_id)).athlete_id
    assert _nominate(client, admin_token, league_id, session_id, keeper_id)["status"] == "open"


def test_declining_or_ending_with_a_pending_swap_is_blocked_while_the_market_is_closed(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Rinunciare allo scambio (o terminare la sessione) ora può assegnare e addebitare:
    a mercato chiuso non si fa, come per lo scambio stesso."""
    admin_token, _ = _register_and_login(client, "live.swapfb.closed.admin@example.com")
    runner_token, runner_id = _register_and_login(client, "live.swapfb.closed.runner@example.com")
    leader_token, leader_id = _register_and_login(client, "live.swapfb.closed.leader@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Rinuncia Chiusa")
    _add_member(db_session, league_id, runner_id)
    _add_member(db_session, league_id, leader_id)
    session_id, lot_id = _pending_swap_lot(
        client,
        db_session,
        admin_token,
        league_id,
        leader_token,
        [(runner_token, 10), (leader_token, 20)],
        name="Portiere Mercato Chiuso",
    )
    admin = {"Authorization": f"Bearer {admin_token}"}
    client.post(f"/leagues/{league_id}/mercato/stato", headers=admin, json={"open": False})

    declined = client.post(
        f"{_live_base(league_id, session_id)}/lotti/{lot_id}/rinuncia-scambio",
        headers={"Authorization": f"Bearer {leader_token}"},
    )
    assert declined.status_code == 400
    assert declined.json()["code"] == "market_closed"
    ended = client.post(f"{_live_base(league_id, session_id)}/termina", headers=admin)
    assert ended.status_code == 400
    assert ended.json()["code"] == "market_closed"
    db_session.expire_all()
    assert db_session.get(MarketLiveLot, UUID(lot_id)).status.value == "pending_swap"
    assert _win_ledger_entries(db_session, lot_id) == []

    client.post(f"/leagues/{league_id}/mercato/stato", headers=admin, json={"open": True})
    ended = client.post(f"{_live_base(league_id, session_id)}/termina", headers=admin)
    assert ended.status_code == 200, ended.json()
    assert _balance(client, runner_token, league_id) == 990
