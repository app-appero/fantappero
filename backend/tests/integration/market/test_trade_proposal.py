"""Integration tests for trade proposal creation (EP08-05 / FR-MKT-03)."""

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
    client: TestClient, league_id: str, token: str, slot_index: int, athlete: Athlete
) -> str:
    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"}
    ).json()
    team_id = rosa["id"]
    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 0},
    )
    assert response.status_code == 200
    return team_id


def _future_iso(hours: int = 24) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def test_create_trade_proposal_validates_ownership_on_both_sides(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "trade.owner@example.com")
    member_token, member_id = _register_and_login(client, "trade.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Scambi")
    _add_member(db_session, league_id, member_id)

    proposer_athlete = _seed_athlete(db_session, 9501, "Offerto Dal Proponente")
    recipient_athlete = _seed_athlete(db_session, 9502, "Richiesto Al Destinatario")
    not_owned_athlete = _seed_athlete(db_session, 9503, "Non Posseduto")

    _own_athlete_at_slot(client, league_id, owner_token, 0, proposer_athlete)
    recipient_team_id = _own_athlete_at_slot(client, league_id, member_token, 0, recipient_athlete)

    wrong_offer = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredAthleteIds": [str(not_owned_athlete.id)],
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    )
    assert wrong_offer.status_code == 400
    assert wrong_offer.json()["code"] == "trade_athlete_not_owned"

    ok = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredAthleteIds": [str(proposer_athlete.id)],
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    )
    assert ok.status_code == 201
    body = ok.json()
    assert body["status"] == "proposed"
    assert body["offeredAthletes"] == [
        {"id": str(proposer_athlete.id), "name": "Offerto Dal Proponente"}
    ]
    assert body["requestedAthletes"] == [
        {"id": str(recipient_athlete.id), "name": "Richiesto Al Destinatario"}
    ]

    # Both sides can see it: proposer's "sent" and recipient's "received" list.
    proposer_list = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert len(proposer_list.json()["proposals"]) == 1
    recipient_list = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert len(recipient_list.json()["proposals"]) == 1


def test_trade_proposal_rejects_disabled_trades_and_insufficient_credits(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "trade.disabled@example.com")
    member_token, member_id = _register_and_login(client, "trade.disabled.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Scambi Disattivati")
    _add_member(db_session, league_id, member_id)
    recipient_athlete = _seed_athlete(db_session, 9504, "Destinatario Player")
    recipient_team_id = _own_athlete_at_slot(
        client, league_id, member_token, 0, recipient_athlete
    )

    rules = client.get(
        f"/leagues/{league_id}", headers={"Authorization": f"Bearer {owner_token}"}
    ).json()["rules"]
    client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "presetName": "standard",
            "participantCount": rules["participantCount"],
            "roster": rules["roster"],
            "totalCredits": rules["totalCredits"],
            "options": {"allowTrades": False, "allowManualInvites": True},
        },
    )

    disabled = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 50,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    )
    assert disabled.status_code == 400
    assert disabled.json()["code"] == "trades_disabled"

    client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "presetName": "standard",
            "participantCount": rules["participantCount"],
            "roster": rules["roster"],
            "totalCredits": rules["totalCredits"],
            "options": {"allowTrades": True, "allowManualInvites": True},
        },
    )
    overdraw = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 5000,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    )
    assert overdraw.status_code == 400
    assert overdraw.json()["code"] == "insufficient_credits"


def test_trade_proposal_rejects_self_trade_and_empty_sides(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "trade.self@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Scambio Vuoto")
    athlete = _seed_athlete(db_session, 9505, "Self Trade Player")
    own_team_id = _own_athlete_at_slot(client, league_id, owner_token, 0, athlete)

    self_trade = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipientTeamId": own_team_id,
            "offeredCredits": 10,
            "requestedCredits": 10,
            "expiresAt": _future_iso(),
        },
    )
    assert self_trade.status_code == 400
    assert self_trade.json()["code"] == "trade_same_team"

    member_token, member_id = _register_and_login(client, "trade.self.member@example.com")
    _add_member(db_session, league_id, member_id)
    recipient_team_id = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {member_token}"}
    ).json()["id"]

    empty_offer = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "requestedCredits": 10,
            "expiresAt": _future_iso(),
        },
    )
    assert empty_offer.status_code == 400
    assert empty_offer.json()["code"] == "trade_offer_empty"


def test_proposer_can_cancel_own_proposal_but_not_others(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "trade.cancel.owner@example.com")
    member_token, member_id = _register_and_login(client, "trade.cancel.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Annulla Scambio")
    _add_member(db_session, league_id, member_id)
    recipient_athlete = _seed_athlete(db_session, 9506, "Destinatario Annulla")
    recipient_team_id = _own_athlete_at_slot(
        client, league_id, member_token, 0, recipient_athlete
    )

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 20,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    )
    proposal_id = proposal.json()["id"]

    forbidden = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal_id}/annulla",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert forbidden.status_code == 400
    assert forbidden.json()["code"] == "trade_cancel_forbidden"

    cancelled = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal_id}/annulla",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    again = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal_id}/annulla",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert again.status_code == 400
    assert again.json()["code"] == "trade_not_cancellable"


def test_expired_proposal_reads_as_expired_without_a_write(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "trade.expired@example.com")
    member_token, member_id = _register_and_login(client, "trade.expired.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Scambio Scaduto")
    _add_member(db_session, league_id, member_id)
    recipient_athlete = _seed_athlete(db_session, 9507, "Destinatario Scaduto")
    recipient_team_id = _own_athlete_at_slot(
        client, league_id, member_token, 0, recipient_athlete
    )

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 15,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(hours=1),
        },
    )
    proposal_id = proposal.json()["id"]

    row = db_session.get(TradeProposal, UUID(proposal_id))
    assert row is not None
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    detail = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal_id}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "expired"


def test_concurrent_cancel_attempts_only_one_succeeds(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, owner_id = _register_and_login(client, "trade.conc@example.com")
    member_token, member_id = _register_and_login(client, "trade.conc.member@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Concorrenza Scambio")
    _add_member(db_session, league_id, member_id)
    recipient_athlete = _seed_athlete(db_session, 9508, "Destinatario Concorrenza")
    recipient_team_id = _own_athlete_at_slot(
        client, league_id, member_token, 0, recipient_athlete
    )

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 30,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    )
    proposal_id = proposal.json()["id"]

    def _cancel(_index: int) -> int:
        response = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte/{proposal_id}/annulla",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(_cancel, range(4)))

    assert statuses.count(200) == 1
    assert statuses.count(400) == 3
