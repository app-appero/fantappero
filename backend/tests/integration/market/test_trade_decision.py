"""Integration tests for trade accept/reject/counter (EP08-06 / FR-MKT-03)."""

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
from market.models import TradeProposal
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
    role: FantasyRole = FantasyRole.D,
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


def _own_athlete_at_slot(
    client: TestClient,
    league_id: str,
    token: str,
    slot_index: int,
    athlete: Athlete,
    *,
    purchase_credits: int = 0,
) -> str:
    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"}
    ).json()
    team_id = rosa["id"]
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": purchase_credits},
    )
    assert response.status_code == 200
    return team_id


def _future_iso(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _propose(
    client: TestClient,
    league_id: str,
    token: str,
    *,
    recipient_team_id: str,
    offered_athlete_ids: list[str] | None = None,
    requested_athlete_ids: list[str] | None = None,
    offered_credits: int = 0,
    requested_credits: int = 0,
) -> dict:
    response = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredAthleteIds": offered_athlete_ids or [],
            "requestedAthleteIds": requested_athlete_ids or [],
            "offeredCredits": offered_credits,
            "requestedCredits": requested_credits,
            "expiresAt": _future_iso(),
        },
    )
    assert response.status_code == 201
    return response.json()


def test_accept_swaps_players_and_credits_atomically(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    proposer_token, proposer_id = _register_and_login(client, "decide.acc.p@example.com")
    recipient_token, recipient_id = _register_and_login(client, "decide.acc.r@example.com")
    league_id = _create_league(client, proposer_token, competition_ids, "Lega Accetta Scambio")
    _add_member(db_session, league_id, recipient_id)

    proposer_athlete = _seed_athlete(db_session, 9601, "Offerto Proponente")
    recipient_athlete = _seed_athlete(db_session, 9602, "Offerto Destinatario")
    proposer_team_id = _own_athlete_at_slot(
        client, league_id, proposer_token, 0, proposer_athlete, purchase_credits=100
    )
    recipient_team_id = _own_athlete_at_slot(
        client, league_id, recipient_token, 0, recipient_athlete, purchase_credits=100
    )

    proposal = _propose(
        client,
        league_id,
        proposer_token,
        recipient_team_id=recipient_team_id,
        offered_athlete_ids=[str(proposer_athlete.id)],
        requested_athlete_ids=[str(recipient_athlete.id)],
        offered_credits=40,
        requested_credits=10,
    )

    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    proposer_slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(proposer_team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    recipient_slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(recipient_team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert proposer_slot.athlete_id == recipient_athlete.id
    assert recipient_slot.athlete_id == proposer_athlete.id

    proposer_account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(proposer_team_id))
    )
    recipient_account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(recipient_team_id))
    )
    # Both teams paid 100 credits for their initial roster.purchase, then
    # proposer: -40 sent, +10 received; recipient: -10 sent, +40 received.
    assert proposer_account.balance == 1000 - 100 - 40 + 10
    assert recipient_account.balance == 1000 - 100 - 10 + 40

    sent_entries = db_session.scalars(
        select(CreditLedgerEntry).where(
            CreditLedgerEntry.reason == CreditLedgerReason.MARKET_TRADE_CREDITS_SENT,
            CreditLedgerEntry.account_id.in_([proposer_account.id, recipient_account.id]),
        )
    ).all()
    assert len(sent_entries) == 2


def test_accept_queues_player_instead_of_failing_when_role_quota_exceeded(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """EP08-10: a role-quota overflow no longer blocks the trade; the incoming
    player is assigned but flagged as exceeding the quota, in attesa until the
    coach releases someone of that role."""
    proposer_token, proposer_id = _register_and_login(client, "decide.q.p@example.com")
    recipient_token, recipient_id = _register_and_login(client, "decide.q.r@example.com")
    league_id = _create_league(client, proposer_token, competition_ids, "Lega Scambio Quota")
    _add_member(db_session, league_id, recipient_id)

    # Standard preset caps goalkeepers at 3; fill the proposer's 3 already.
    for index, provider_id in enumerate((9610, 9611, 9612)):
        gk = _seed_athlete(db_session, provider_id, f"Portiere {index}", role=FantasyRole.P)
        proposer_team_id = _own_athlete_at_slot(client, league_id, proposer_token, index, gk)
    fourth_gk = _seed_athlete(db_session, 9613, "Quarto Portiere", role=FantasyRole.P)
    recipient_team_id = _own_athlete_at_slot(client, league_id, recipient_token, 0, fourth_gk)

    proposal = _propose(
        client,
        league_id,
        proposer_token,
        recipient_team_id=recipient_team_id,
        offered_credits=50,
        requested_athlete_ids=[str(fourth_gk.id)],
    )

    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    # The goalkeeper moved to the proposer, flagged as over the role quota (in attesa).
    proposer_slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(proposer_team_id),
            FantasyRosterSlot.athlete_id == fourth_gk.id,
        )
    )
    assert proposer_slot is not None
    assert proposer_slot.exceeds_role_quota is True

    proposer_account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(proposer_team_id))
    )
    assert proposer_account.balance == 1000 - 50

    row = db_session.get(TradeProposal, UUID(proposal["id"]))
    assert row is not None
    assert row.status.value == "accepted"


def test_accept_creates_overflow_slot_instead_of_failing_when_roster_has_no_free_space(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """EP08-10 bis: an unbalanced trade (give fewer than you receive) no longer
    fails with "la rosa non ha spazio" when the proposer's roster is already
    full — an extra slot is created for the incoming player instead, flagged
    as in excess, in attesa until the coach releases someone."""
    proposer_token, proposer_id = _register_and_login(client, "decide.cap.p@example.com")
    recipient_token, recipient_id = _register_and_login(client, "decide.cap.r@example.com")
    league_id = _create_league(client, proposer_token, competition_ids, "Lega Scambio Capienza")
    _add_member(db_session, league_id, recipient_id)

    # Standard preset: 3 P, 11 D, 11 C, 10 A — fill the proposer's roster completely.
    role_counts = (
        (FantasyRole.P, 3),
        (FantasyRole.D, 11),
        (FantasyRole.C, 11),
        (FantasyRole.A, 10),
    )
    provider_id = 9700
    slot_index = 0
    offered_athlete: Athlete | None = None
    proposer_team_id = ""
    for role, count in role_counts:
        for position in range(count):
            athlete = _seed_athlete(db_session, provider_id, f"{role.value}{position}", role=role)
            proposer_team_id = _own_athlete_at_slot(
                client, league_id, proposer_token, slot_index, athlete
            )
            if role is FantasyRole.D and position == 0:
                offered_athlete = athlete
            provider_id += 1
            slot_index += 1
    assert offered_athlete is not None

    requested_athletes = [
        _seed_athlete(db_session, provider_id + i, f"RichiestoA{i}", role=FantasyRole.A)
        for i in range(2)
    ]
    recipient_team_id = _own_athlete_at_slot(
        client, league_id, recipient_token, 0, requested_athletes[0]
    )
    _own_athlete_at_slot(client, league_id, recipient_token, 1, requested_athletes[1])

    proposal = _propose(
        client,
        league_id,
        proposer_token,
        recipient_team_id=recipient_team_id,
        offered_athlete_ids=[str(offered_athlete.id)],
        requested_athlete_ids=[str(athlete.id) for athlete in requested_athletes],
    )

    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"

    proposer_slots = list(
        db_session.scalars(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.fantasy_team_id == UUID(proposer_team_id),
            )
        ).all()
    )
    # 35 original + 1 extra created for the player with nowhere left to go.
    assert len(proposer_slots) == 36
    occupied = [slot for slot in proposer_slots if slot.athlete_id is not None]
    assert len(occupied) == 36
    flagged = [slot for slot in occupied if slot.exceeds_role_quota]
    # Forwards go from 10 (at cap) to 12: both incoming attackers are in excess.
    assert len(flagged) == 2
    assert {slot.athlete_id for slot in flagged} == {athlete.id for athlete in requested_athletes}

    row = db_session.get(TradeProposal, UUID(proposal["id"]))
    assert row is not None
    assert row.status.value == "accepted"

    # Releasing one flagged attacker resolves both the capacity overflow (back to
    # 35 occupied slots) and one unit of the role overflow (forwards: 12 -> 11,
    # still one over the cap of 10) — exactly one of the two stays flagged.
    released_slot_index = flagged[0].slot_index
    released = client.delete(
        f"/leagues/{league_id}/amministrazione/squadre/{proposer_team_id}/slot/{released_slot_index}",
        headers={"Authorization": f"Bearer {proposer_token}"},
    )
    assert released.status_code == 200

    db_session.expire_all()
    remaining_slots = list(
        db_session.scalars(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.fantasy_team_id == UUID(proposer_team_id),
            )
        ).all()
    )
    occupied_after = [slot for slot in remaining_slots if slot.athlete_id is not None]
    assert len(occupied_after) == 35
    flagged_after = [slot for slot in occupied_after if slot.exceeds_role_quota]
    assert len(flagged_after) == 1


def test_stale_overflow_flag_is_cleared_when_the_team_is_back_within_quota(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """EP08-10: a slot still flagged "in attesa" after the team is back within
    its role quota (3 goalkeepers out of 3) is healed on the next roster read."""
    token, _ = _register_and_login(client, "decide.stale.p@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Flag Stantio")
    team_id = ""
    athletes = []
    for index, provider_id in enumerate((9810, 9811, 9812)):
        gk = _seed_athlete(db_session, provider_id, f"Portiere S{index}", role=FantasyRole.P)
        athletes.append(gk)
        team_id = _own_athlete_at_slot(client, league_id, token, index, gk)
    stale = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.athlete_id == athletes[1].id,
        )
    )
    stale.exceeds_role_quota = True
    db_session.commit()

    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    assert rosa.status_code == 200
    flags = [slot["exceedsRoleQuota"] for slot in rosa.json()["slots"] if slot["athleteId"]]
    assert flags == [False, False, False]


def test_reject_marks_terminal_and_is_visible_to_both_sides(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    proposer_token, proposer_id = _register_and_login(client, "decide.rej.p@example.com")
    recipient_token, recipient_id = _register_and_login(client, "decide.rej.r@example.com")
    league_id = _create_league(client, proposer_token, competition_ids, "Lega Rifiuta Scambio")
    _add_member(db_session, league_id, recipient_id)
    recipient_athlete = _seed_athlete(db_session, 9620, "Player Rifiutato")
    recipient_team_id = _own_athlete_at_slot(
        client, league_id, recipient_token, 0, recipient_athlete
    )

    proposal = _propose(
        client,
        league_id,
        proposer_token,
        recipient_team_id=recipient_team_id,
        offered_credits=25,
        requested_athlete_ids=[str(recipient_athlete.id)],
    )

    forbidden = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/rifiuta",
        headers={"Authorization": f"Bearer {proposer_token}"},
    )
    assert forbidden.status_code == 400
    assert forbidden.json()["code"] == "trade_decision_forbidden"

    rejected = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/rifiuta",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    detail = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}",
        headers={"Authorization": f"Bearer {proposer_token}"},
    )
    assert detail.json()["status"] == "rejected"


def test_counter_proposal_flips_roles_and_supersedes_original(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    proposer_token, proposer_id = _register_and_login(client, "decide.ctr.p@example.com")
    recipient_token, recipient_id = _register_and_login(client, "decide.ctr.r@example.com")
    league_id = _create_league(client, proposer_token, competition_ids, "Lega Controproposta")
    _add_member(db_session, league_id, recipient_id)
    proposer_athlete = _seed_athlete(db_session, 9630, "Offerto Iniziale")
    recipient_athlete = _seed_athlete(db_session, 9631, "Richiesto Iniziale")
    proposer_team_id = _own_athlete_at_slot(client, league_id, proposer_token, 0, proposer_athlete)
    recipient_team_id = _own_athlete_at_slot(
        client, league_id, recipient_token, 0, recipient_athlete
    )

    original = _propose(
        client,
        league_id,
        proposer_token,
        recipient_team_id=recipient_team_id,
        offered_athlete_ids=[str(proposer_athlete.id)],
        requested_athlete_ids=[str(recipient_athlete.id)],
        offered_credits=10,
    )

    counter = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{original['id']}/controproponi",
        headers={"Authorization": f"Bearer {recipient_token}"},
        json={
            "offeredAthleteIds": [str(recipient_athlete.id)],
            "requestedAthleteIds": [str(proposer_athlete.id)],
            "requestedCredits": 30,
            "expiresAt": _future_iso(),
        },
    )
    assert counter.status_code == 201
    counter_body = counter.json()
    assert counter_body["proposerTeamId"] == recipient_team_id
    assert counter_body["recipientTeamId"] == proposer_team_id
    assert counter_body["counterOfId"] == original["id"]

    original_after = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte/{original['id']}",
        headers={"Authorization": f"Bearer {proposer_token}"},
    )
    assert original_after.json()["status"] == "countered"

    # The superseded original can no longer be accepted.
    stale_accept = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{original['id']}/accetta",
        headers={"Authorization": f"Bearer {recipient_token}"},
    )
    assert stale_accept.status_code == 400
    assert stale_accept.json()["code"] == "trade_not_actionable"


def test_concurrent_accept_and_reject_only_one_transition_wins(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    proposer_token, proposer_id = _register_and_login(client, "decide.cc.p@example.com")
    recipient_token, recipient_id = _register_and_login(client, "decide.cc.r@example.com")
    league_id = _create_league(client, proposer_token, competition_ids, "Lega Concorrenza")
    _add_member(db_session, league_id, recipient_id)
    recipient_athlete = _seed_athlete(db_session, 9640, "Player Concorrenza")
    recipient_team_id = _own_athlete_at_slot(
        client, league_id, recipient_token, 0, recipient_athlete
    )

    proposal = _propose(
        client,
        league_id,
        proposer_token,
        recipient_team_id=recipient_team_id,
        offered_credits=15,
        requested_athlete_ids=[str(recipient_athlete.id)],
    )

    def _accept(_index: int) -> int:
        response = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
            headers={"Authorization": f"Bearer {recipient_token}"},
        )
        return response.status_code

    def _reject(_index: int) -> int:
        response = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/rifiuta",
            headers={"Authorization": f"Bearer {recipient_token}"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [
            pool.submit(_accept, 0),
            pool.submit(_reject, 1),
            pool.submit(_accept, 2),
            pool.submit(_reject, 3),
        ]
        statuses = [future.result() for future in futures]

    assert statuses.count(200) == 1
    assert statuses.count(400) == 3

    row = db_session.get(TradeProposal, UUID(proposal["id"]))
    assert row is not None
    assert row.status.value in {"accepted", "rejected"}
