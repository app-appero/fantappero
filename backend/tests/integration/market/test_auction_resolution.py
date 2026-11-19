"""Integration tests for sealed-bid auction resolution and tiebreaks (EP08-02)."""

from __future__ import annotations

import random
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import CreditLedgerReason, FantasyRole, LeagueAuditAction, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import CreditAccount, CreditLedgerEntry, FantasyRosterSlot
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from market.models import MarketBid, MarketSession
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

    # Nello spareggio non si scende sotto l'importo del pareggio (pareggiarlo resta ammesso).
    lower = _bid(client, league_id, tiebreak_id, admin_token, athlete.id, 50)
    assert lower.status_code == 400
    assert lower.json()["code"] == "tiebreak_bid_below_tied_amount"
    assert _bid(client, league_id, tiebreak_id, member_token, athlete.id, 100).status_code == 200

    # A tied team can now rebid inside the tiebreak session.
    rebid = _bid(client, league_id, tiebreak_id, admin_token, athlete.id, 120)
    assert rebid.status_code == 200

    # Le due squadre in parità sono avvisate dello spareggio; chi non c'entra no.
    for user_id in (admin_id, member_id):
        titles = [
            row.title
            for row in db_session.scalars(
                select(Notification).where(Notification.user_id == user_id)
            ).all()
        ]
        assert "Spareggio aperto" in titles
    outsider_titles = [
        row.title
        for row in db_session.scalars(
            select(Notification).where(Notification.user_id == outsider_id)
        ).all()
    ]
    assert "Spareggio aperto" not in outsider_titles


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


def test_winning_a_fourth_goalkeeper_enters_the_roster_flagged_instead_of_losing_the_bid(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """EP08-10 bis: a role quota already full no longer loses the sealed bid —
    the player joins the roster flagged "in attesa" until the coach releases someone."""
    admin_token, _ = _register_and_login(client, "res.ovf.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Esubero Asta")
    team_id = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {admin_token}"}
    ).json()["id"]
    for index, provider_id in enumerate((9301, 9302, 9303)):
        gk = _seed_athlete(db_session, provider_id, f"Portiere {index}", role=FantasyRole.P)
        placed = client.put(
            f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{index}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"athleteId": str(gk.id), "purchaseCredits": 0},
        )
        assert placed.status_code == 200
    fourth = _seed_athlete(db_session, 9304, "Quarto Portiere", role=FantasyRole.P)

    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, fourth.id, 40).status_code == 200

    resolution = _close_and_resolve(client, league_id, session_id, admin_token)
    assert resolution.status_code == 200
    assert resolution.json()["outcomes"][0]["outcome"] == "assigned"

    won_slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == fourth.id)
    )
    assert won_slot is not None
    assert won_slot.exceeds_role_quota is True
    assert won_slot.purchase_credits == 40


def test_new_session_is_rejected_while_a_tiebreak_session_is_active(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, _ = _register_and_login(client, "res.tie.block.admin@example.com")
    member_token, member_id = _register_and_login(client, "res.tie.block.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Spareggio Bloccato")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(
        db_session, random.randint(100_000_000, 2_000_000_000), "Spareggio Aperto"
    )

    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, athlete.id, 100).status_code == 200
    assert _bid(client, league_id, session_id, member_token, athlete.id, 100).status_code == 200
    assert _close_and_resolve(client, league_id, session_id, admin_token).status_code == 200

    now = datetime.now(UTC)
    blocked = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": (now - timedelta(minutes=1)).isoformat(),
            "closesAt": (now + timedelta(hours=1)).isoformat(),
        },
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "market_session_already_active"


def test_unassignable_top_bid_falls_to_the_runner_up_with_enough_credits(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Il coach non ha più crediti per la seconda offerta vinta: va al secondo offerente."""
    admin_token, _ = _register_and_login(client, "res.runner.admin@example.com")
    member_token, member_id = _register_and_login(client, "res.runner.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Seconda Offerta")
    _add_member(db_session, league_id, member_id)
    first = _seed_athlete(db_session, 9401, "Primo Colpo")
    second = _seed_athlete(db_session, 9402, "Secondo Colpo")

    session_id = _create_open_session(client, admin_token, league_id)
    assert _bid(client, league_id, session_id, admin_token, first.id, 900).status_code == 200
    assert _bid(client, league_id, session_id, admin_token, second.id, 800).status_code == 200
    assert _bid(client, league_id, session_id, member_token, second.id, 120).status_code == 200

    resolution = _close_and_resolve(client, league_id, session_id, admin_token)
    assert resolution.status_code == 200

    def owner_of(athlete_id) -> str | None:
        slot = db_session.scalar(
            select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete_id)
        )
        if slot is None:
            return None
        membership = db_session.get(LeagueMembership, slot.fantasy_team.membership_id)
        return str(membership.user_id)

    db_session.expire_all()
    assert owner_of(second.id) == str(member_id)


# -- Spareggio unico (decisione di Rosario del 19/11) ------------------------------------------


def _team_id(client: TestClient, league_id: str, token: str) -> str:
    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    assert rosa.status_code == 200
    return rosa.json()["id"]


def _balance(client: TestClient, league_id: str, token: str) -> int:
    response = client.get(
        f"/leagues/{league_id}/crediti", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    return response.json()["balance"]


def _admin_adjust_credits(
    client: TestClient, admin_token: str, league_id: str, team_id: str, amount: int, tx: str
) -> None:
    response = client.post(
        f"/leagues/{league_id}/amministrazione/crediti/movimenti",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "fantasyTeamId": team_id,
            "amount": amount,
            "transactionId": tx,
            "note": "Correzione di prova",
        },
    )
    assert response.status_code == 200, response.json()


def _titles(db_session: Session, user_id: UUID) -> list[str]:
    return [
        row.title
        for row in db_session.scalars(
            select(Notification).where(Notification.user_id == user_id)
        ).all()
    ]


def _notification(db_session: Session, user_id: UUID, title: str) -> list[Notification]:
    return list(
        db_session.scalars(
            select(Notification).where(Notification.user_id == user_id, Notification.title == title)
        ).all()
    )


def _resolved_audit(db_session: Session, session_id: str) -> LeagueAuditEvent:
    rows = [
        row
        for row in db_session.scalars(
            select(LeagueAuditEvent).where(
                LeagueAuditEvent.action == LeagueAuditAction.MARKET_SESSION_RESOLVED
            )
        ).all()
        if (row.details or {}).get("sessionId") == session_id
    ]
    assert len(rows) == 1
    return rows[0]


def _open_tiebreak(
    client: TestClient,
    league_id: str,
    admin_token: str,
    tokens: list[str],
    athlete_id: UUID,
    *,
    amount: int = 100,
) -> str:
    """Sessione a buste con le squadre di ``tokens`` in parità: ritorna l'id dello spareggio."""
    session_id = _create_open_session(client, admin_token, league_id)
    for token in tokens:
        assert _bid(client, league_id, session_id, token, athlete_id, amount).status_code == 200
    resolution = _close_and_resolve(client, league_id, session_id, admin_token)
    assert resolution.status_code == 200
    outcome = resolution.json()["outcomes"][0]
    assert outcome["outcome"] == "tiebreak"
    return outcome["tiebreakSessionId"]


def _new_auction_session_status(client: TestClient, admin_token: str, league_id: str) -> int:
    now = datetime.now(UTC)
    response = client.post(
        f"/leagues/{league_id}/mercato/asta/sessioni",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "opensAt": (now - timedelta(minutes=1)).isoformat(),
            "closesAt": (now + timedelta(hours=1)).isoformat(),
        },
    )
    return response.status_code


def _random_provider_id() -> int:
    return random.randint(100_000_000, 2_000_000_000)


def test_tiebreak_tied_again_goes_to_the_first_bid_and_unblocks_the_market(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Spareggio di nuovo in parità: niente secondo spareggio, vince chi ha inviato per primo.

    Conta l'ultimo invio: chi riinvia la stessa offerta passa dopo l'altro.
    """
    admin_token, admin_id = _register_and_login(client, "res.tie2.admin@example.com")
    member_token, member_id = _register_and_login(client, "res.tie2.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Spareggio Unico")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, _random_provider_id(), "Conteso Due Volte")
    admin_team = _team_id(client, league_id, admin_token)
    member_team = _team_id(client, league_id, member_token)

    tiebreak_id = _open_tiebreak(
        client, league_id, admin_token, [admin_token, member_token], athlete.id
    )
    assert _bid(client, league_id, tiebreak_id, member_token, athlete.id, 120).status_code == 200
    assert _bid(client, league_id, tiebreak_id, admin_token, athlete.id, 120).status_code == 200
    # Il membro riinvia la stessa offerta: ora la sua è l'ultima arrivata.
    assert _bid(client, league_id, tiebreak_id, member_token, athlete.id, 120).status_code == 200

    resolution = _close_and_resolve(client, league_id, tiebreak_id, admin_token)
    assert resolution.status_code == 200
    outcome = resolution.json()["outcomes"][0]
    assert outcome["outcome"] == "assigned"
    assert outcome["winningTeamId"] == admin_team
    assert outcome["amountCredits"] == 120
    assert outcome["tiebreakSessionId"] is None

    db_session.expire_all()
    # Nessun nuovo spareggio.
    assert (
        db_session.scalars(
            select(MarketSession).where(MarketSession.parent_session_id == UUID(tiebreak_id))
        ).all()
        == []
    )
    bids = {
        str(row.fantasy_team_id): row.status.value
        for row in db_session.scalars(
            select(MarketBid).where(MarketBid.session_id == UUID(tiebreak_id))
        ).all()
    }
    assert bids == {admin_team: "won", member_team: "lost"}
    slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete.id)
    )
    assert slot is not None
    assert str(slot.fantasy_team_id) == admin_team
    assert slot.purchase_credits == 120
    assert _balance(client, league_id, admin_token) == 880
    assert _balance(client, league_id, member_token) == 1000

    # Le solite notifiche di esito.
    assert len(_notification(db_session, admin_id, "Busta aggiudicata")) == 1
    lost = _notification(db_session, member_id, "Busta non aggiudicata")
    assert len(lost) == 1
    assert "inviata per prima" in lost[0].body
    assert _titles(db_session, member_id).count("Spareggio aperto") == 1  # solo il primo

    details = _resolved_audit(db_session, tiebreak_id).details
    assert details["tiebreakRule"] == "first_bid"
    assert details["tiebreaksOpened"] == 0
    assert details["winners"] == [
        {"fantasyTeamId": admin_team, "athleteId": str(athlete.id), "amountCredits": 120}
    ]
    assert details["tiebreakResults"] == [
        {
            "athleteId": str(athlete.id),
            "tiedAmountCredits": 120,
            "teamIds": [admin_team, member_team],
            "winnerTeamId": admin_team,
        }
    ]

    # Il mercato non resta bloccato: si può creare una nuova sessione.
    assert _new_auction_session_status(client, admin_token, league_id) == 201


def test_tiebreak_tied_again_skips_a_first_bid_that_cannot_be_paid(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """La prima offerta in parità non è più coperta dai crediti: vince la successiva in parità."""
    admin_token, admin_id = _register_and_login(client, "res.tie2.poor.admin@example.com")
    member_token, member_id = _register_and_login(client, "res.tie2.poor.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Spareggio Senza Crediti")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, _random_provider_id(), "Conteso Senza Crediti")
    admin_team = _team_id(client, league_id, admin_token)
    member_team = _team_id(client, league_id, member_token)

    tiebreak_id = _open_tiebreak(
        client, league_id, admin_token, [admin_token, member_token], athlete.id
    )
    assert _bid(client, league_id, tiebreak_id, admin_token, athlete.id, 150).status_code == 200
    assert _bid(client, league_id, tiebreak_id, member_token, athlete.id, 150).status_code == 200
    _admin_adjust_credits(client, admin_token, league_id, admin_team, -900, "tie2-poor")

    resolution = _close_and_resolve(client, league_id, tiebreak_id, admin_token)
    assert resolution.status_code == 200
    outcome = resolution.json()["outcomes"][0]
    assert outcome["outcome"] == "assigned"
    assert outcome["winningTeamId"] == member_team
    assert outcome["amountCredits"] == 150

    db_session.expire_all()
    assert (
        db_session.scalars(
            select(MarketSession).where(MarketSession.parent_session_id == UUID(tiebreak_id))
        ).all()
        == []
    )
    assert _balance(client, league_id, member_token) == 850
    assert _balance(client, league_id, admin_token) == 100
    lost = _notification(db_session, admin_id, "Busta non aggiudicata")
    assert len(lost) == 1
    assert "non è stato possibile assegnarlo" in lost[0].body
    assert len(_notification(db_session, member_id, "Busta aggiudicata")) == 1
    details = _resolved_audit(db_session, tiebreak_id).details
    assert details["tiebreakRule"] == "first_bid"
    assert details["tiebreakResults"][0]["teamIds"] == [admin_team, member_team]
    assert details["tiebreakResults"][0]["winnerTeamId"] == member_team
    assert _new_auction_session_status(client, admin_token, league_id) == 201


def test_waiver_tiebreak_tied_again_goes_to_the_first_bid(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Stessa regola per lo spareggio degli svincolati (stesso percorso di risoluzione)."""
    admin_token, admin_id = _register_and_login(client, "res.tie2.waiver.admin@example.com")
    member_token, member_id = _register_and_login(client, "res.tie2.waiver.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Spareggio Svincolati")
    _add_member(db_session, league_id, member_id)
    admin_team = _team_id(client, league_id, admin_token)
    member_team = _team_id(client, league_id, member_token)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    release: dict[str, str] = {}
    for token, team_id in ((admin_token, admin_team), (member_token, member_team)):
        owned = _seed_athlete(db_session, _random_provider_id(), f"Da Svincolare {team_id[:8]}")
        placed = client.put(
            f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
            headers=admin_headers,
            json={"athleteId": str(owned.id), "purchaseCredits": 0},
        )
        assert placed.status_code == 200, placed.json()
        release[token] = str(owned.id)
    free_agent = _seed_athlete(db_session, _random_provider_id(), "Svincolato Conteso")
    base = f"/leagues/{league_id}/mercato/svincoli/sessioni"

    def waiver_bid(session_id: str, token: str, amount: int) -> None:
        response = client.put(
            f"{base}/{session_id}/offerte/{free_agent.id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"amountCredits": amount, "releaseAthleteId": release[token]},
        )
        assert response.status_code == 200, response.json()

    def close_and_resolve(session_id: str) -> dict:
        assert client.post(f"{base}/{session_id}/chiudi", headers=admin_headers).status_code == 200
        resolved = client.post(f"{base}/{session_id}/risolvi", headers=admin_headers)
        assert resolved.status_code == 200, resolved.json()
        return resolved.json()

    def create_waiver_session(minutes: int) -> int | str:
        now = datetime.now(UTC)
        response = client.post(
            base,
            headers=admin_headers,
            json={
                "opensAt": (now - timedelta(minutes=1)).isoformat(),
                "closesAt": (now + timedelta(minutes=minutes)).isoformat(),
            },
        )
        return response.json()["id"] if response.status_code == 201 else response.status_code

    waiver_id = create_waiver_session(1)
    assert isinstance(waiver_id, str)
    waiver_bid(waiver_id, admin_token, 50)
    waiver_bid(waiver_id, member_token, 50)
    first = close_and_resolve(waiver_id)["outcomes"][0]
    assert first["outcome"] == "tiebreak"
    tiebreak_id = first["tiebreakSessionId"]
    assert create_waiver_session(60) == 400  # lo spareggio aperto blocca il mercato

    waiver_bid(tiebreak_id, member_token, 60)
    waiver_bid(tiebreak_id, admin_token, 60)
    outcome = close_and_resolve(tiebreak_id)["outcomes"][0]
    assert outcome["outcome"] == "assigned"
    assert outcome["winningTeamId"] == member_team
    assert outcome["amountCredits"] == 60

    db_session.expire_all()
    assert (
        db_session.scalars(
            select(MarketSession).where(MarketSession.parent_session_id == UUID(tiebreak_id))
        ).all()
        == []
    )
    slot = db_session.scalar(
        select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == free_agent.id)
    )
    assert slot is not None
    assert str(slot.fantasy_team_id) == member_team

    def owner(athlete_id: str) -> FantasyRosterSlot | None:
        return db_session.scalar(
            select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == UUID(athlete_id))
        )

    # Esce dalla rosa solo il calciatore indicato dal vincitore.
    assert owner(release[member_token]) is None
    assert owner(release[admin_token]) is not None
    assert _balance(client, league_id, member_token) == 940
    assert _balance(client, league_id, admin_token) == 1000
    assert len(_notification(db_session, member_id, "Busta aggiudicata")) == 1
    assert len(_notification(db_session, admin_id, "Busta non aggiudicata")) == 1
    assert _resolved_audit(db_session, tiebreak_id).details["tiebreakRule"] == "first_bid"
    assert isinstance(create_waiver_session(60), str)


# -- "Spareggio annullato" a tutte le squadre in parità -----------------------------------------


def _admin_assign(
    client: TestClient, admin_token: str, league_id: str, team_id: str, athlete_id: UUID
) -> None:
    """L'amministratore mette a mano il calciatore conteso nel primo slot (vuoto) di una squadra."""
    placed = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"athleteId": str(athlete_id), "purchaseCredits": 0},
    )
    assert placed.status_code == 200, placed.json()


def _cancelled(db_session: Session, user_id: UUID) -> list[Notification]:
    return _notification(db_session, user_id, "Spareggio annullato")


def test_cancelled_tiebreak_notifies_every_tied_team_except_the_new_owner(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Parità tra A e B, nello spareggio offre solo A, l'admin dà il calciatore a C:
    l'avviso "Spareggio annullato" arriva ad A e anche a B, non a C."""
    a_token, a_id = _register_and_login(client, "res.tiecancel.a@example.com")
    b_token, b_id = _register_and_login(client, "res.tiecancel.b@example.com")
    c_token, c_id = _register_and_login(client, "res.tiecancel.c@example.com")
    league_id = _create_league(client, a_token, competition_ids, "Lega Spareggio Annullato")
    _add_member(db_session, league_id, b_id)
    _add_member(db_session, league_id, c_id)
    athlete = _seed_athlete(db_session, _random_provider_id(), "Conteso Altrove")
    a_team = _team_id(client, league_id, a_token)
    b_team = _team_id(client, league_id, b_token)
    c_team = _team_id(client, league_id, c_token)

    tiebreak_id = _open_tiebreak(client, league_id, a_token, [a_token, b_token], athlete.id)
    assert _bid(client, league_id, tiebreak_id, a_token, athlete.id, 100).status_code == 200
    _admin_assign(client, a_token, league_id, c_team, athlete.id)

    resolution = _close_and_resolve(client, league_id, tiebreak_id, a_token)
    assert resolution.status_code == 200
    assert resolution.json()["outcomes"][0]["outcome"] == "unassigned"

    db_session.expire_all()
    for user_id, team_id in ((a_id, a_team), (b_id, b_team)):
        cancelled = _cancelled(db_session, user_id)
        assert len(cancelled) == 1, user_id
        assert cancelled[0].dedup_key == f"market_tiebreak_cancelled:{tiebreak_id}:{team_id}"
        assert "Conteso Altrove" in cancelled[0].body
    # A non riceve anche il "Busta non aggiudicata" della sua offerta: basta l'annullamento.
    assert _notification(db_session, a_id, "Busta non aggiudicata") == []
    assert _cancelled(db_session, c_id) == []


def test_cancelled_tiebreak_without_bids_still_notifies_the_tied_teams(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Nessuno offre nello spareggio e l'admin dà il calciatore a B (una delle squadre in
    parità): l'annullamento arriva ad A, non a B che ora ha il calciatore."""
    a_token, a_id = _register_and_login(client, "res.tiecancel.nobid.a@example.com")
    b_token, b_id = _register_and_login(client, "res.tiecancel.nobid.b@example.com")
    league_id = _create_league(client, a_token, competition_ids, "Lega Spareggio Senza Offerte")
    _add_member(db_session, league_id, b_id)
    athlete = _seed_athlete(db_session, _random_provider_id(), "Conteso Senza Offerte")
    a_team = _team_id(client, league_id, a_token)
    b_team = _team_id(client, league_id, b_token)

    tiebreak_id = _open_tiebreak(client, league_id, a_token, [a_token, b_token], athlete.id)
    _admin_assign(client, a_token, league_id, b_team, athlete.id)

    resolution = _close_and_resolve(client, league_id, tiebreak_id, a_token)
    assert resolution.status_code == 200
    assert resolution.json()["outcomes"] == []

    db_session.expire_all()
    cancelled = _cancelled(db_session, a_id)
    assert len(cancelled) == 1
    assert cancelled[0].dedup_key == f"market_tiebreak_cancelled:{tiebreak_id}:{a_team}"
    assert _cancelled(db_session, b_id) == []
    # Lo spareggio è risolto: il mercato non è più bloccato.
    assert _new_auction_session_status(client, a_token, league_id) == 201


def test_tiebreak_without_bids_and_player_still_free_notifies_nobody(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Comportamento invariato: spareggio senza offerte, calciatore ancora libero."""
    a_token, a_id = _register_and_login(client, "res.tienobid.a@example.com")
    b_token, b_id = _register_and_login(client, "res.tienobid.b@example.com")
    league_id = _create_league(client, a_token, competition_ids, "Lega Spareggio Deserto")
    _add_member(db_session, league_id, b_id)
    athlete = _seed_athlete(db_session, _random_provider_id(), "Conteso Libero")

    tiebreak_id = _open_tiebreak(client, league_id, a_token, [a_token, b_token], athlete.id)
    resolution = _close_and_resolve(client, league_id, tiebreak_id, a_token)
    assert resolution.status_code == 200
    assert resolution.json()["outcomes"] == []

    db_session.expire_all()
    assert (
        db_session.scalar(
            select(FantasyRosterSlot).where(FantasyRosterSlot.athlete_id == athlete.id)
        )
        is None
    )
    for user_id in (a_id, b_id):
        assert _cancelled(db_session, user_id) == []
        assert _notification(db_session, user_id, "Busta non aggiudicata") == []
    assert _new_auction_session_status(client, a_token, league_id) == 201
