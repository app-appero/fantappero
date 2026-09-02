"""Integration tests for trade admin approval and limits (EP08-07 / FR-MKT-03)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.models import CreditAccount, FantasyRosterSlot
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
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
    db_session: Session, provider_id: int, name: str, *, season_year: int = 2026
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=season_year,
            role=FantasyRole.D,
            mapping_version="v1.0.0",
            provider_position_raw=FantasyRole.D.value,
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


def _set_league_rules(
    client: TestClient,
    league_id: str,
    token: str,
    *,
    require_trade_approval: bool | None = None,
    max_active_trade_proposals_per_team: int | None = None,
) -> dict:
    rules = client.get(
        f"/leagues/{league_id}", headers={"Authorization": f"Bearer {token}"}
    ).json()["rules"]
    body = {
        "presetName": "standard",
        "participantCount": rules["participantCount"],
        "roster": rules["roster"],
        "totalCredits": rules["totalCredits"],
        "options": {
            "allowTrades": True,
            "allowManualInvites": True,
            "requireTradeApproval": (
                require_trade_approval
                if require_trade_approval is not None
                else rules["options"]["requireTradeApproval"]
            ),
        },
    }
    if max_active_trade_proposals_per_team is not None:
        body["maxActiveTradeProposalsPerTeam"] = max_active_trade_proposals_per_team
    response = client.put(
        f"/leagues/{league_id}/amministrazione/regolamento",
        headers={"Authorization": f"Bearer {token}"},
        json=body,
    )
    assert response.status_code == 200
    return response.json()


def test_require_trade_approval_defers_execution_until_admin_acts(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "approve.admin@example.com")
    member_token, member_id = _register_and_login(client, "approve.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Approvazione")
    _add_member(db_session, league_id, member_id)
    recipient_athlete = _seed_athlete(db_session, 9701, "Destinatario Approvazione")
    recipient_team_id = _own_athlete_at_slot(client, league_id, member_token, 0, recipient_athlete)

    rules = _set_league_rules(client, league_id, admin_token, require_trade_approval=True)
    assert rules["options"]["requireTradeApproval"] is True

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 20,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    ).json()

    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "pending_approval"

    # Nothing moved yet: the player is still with the recipient.
    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(recipient_team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot.athlete_id == recipient_athlete.id

    forbidden = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/amministrazione/approva",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert forbidden.status_code == 403

    approved = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/amministrazione/approva",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "executed"

    db_session.expire_all()
    slot_after = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(recipient_team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot_after.athlete_id is None  # moved out to the proposer

    # Already-executed proposals cannot be approved again.
    again = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/amministrazione/approva",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert again.status_code == 400
    assert again.json()["code"] == "trade_not_pending_approval"


def test_admin_can_reject_a_pending_approval_trade(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "approve.rej.admin@example.com")
    member_token, member_id = _register_and_login(client, "approve.rej.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Rifiuto Admin")
    _add_member(db_session, league_id, member_id)
    recipient_athlete = _seed_athlete(db_session, 9702, "Destinatario Rifiuto Admin")
    recipient_team_id = _own_athlete_at_slot(client, league_id, member_token, 0, recipient_athlete)
    _set_league_rules(client, league_id, admin_token, require_trade_approval=True)

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 15,
            "requestedAthleteIds": [str(recipient_athlete.id)],
            "expiresAt": _future_iso(),
        },
    ).json()
    client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/accetta",
        headers={"Authorization": f"Bearer {member_token}"},
    )

    rejected = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal['id']}/amministrazione/rifiuta",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected_by_admin"

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(recipient_team_id))
    )
    assert account is not None
    assert account.balance == 1000  # untouched


def test_max_active_trade_proposals_per_team_is_enforced(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    admin_token, admin_id = _register_and_login(client, "limit.admin@example.com")
    member_token, member_id = _register_and_login(client, "limit.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega Limite Scambi")
    _add_member(db_session, league_id, member_id)
    recipient_team_id = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {member_token}"}
    ).json()["id"]

    rules = _set_league_rules(
        client, league_id, admin_token, max_active_trade_proposals_per_team=2
    )
    assert rules["maxActiveTradeProposalsPerTeam"] == 2

    for _ in range(2):
        response = client.post(
            f"/leagues/{league_id}/mercato/scambi/proposte",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "recipientTeamId": recipient_team_id,
                "offeredCredits": 5,
                "requestedCredits": 5,
                "expiresAt": _future_iso(),
            },
        )
        assert response.status_code == 201

    over_limit = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 5,
            "requestedCredits": 5,
            "expiresAt": _future_iso(),
        },
    )
    assert over_limit.status_code == 400
    assert over_limit.json()["code"] == "trade_active_limit_reached"
