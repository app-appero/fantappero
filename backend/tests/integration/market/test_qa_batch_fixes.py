"""Regressioni dal giro QA su dev: N1 (atomicità), N3 (approvazione visibile), N6 (svincolo)."""

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


def _hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_owner_sees_and_is_notified_of_trades_pending_approval(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, admin_id = _register_and_login(client, "n3.admin@example.com")
    proposer_token, proposer_id = _register_and_login(client, "n3.proposer@example.com")
    recipient_token, recipient_id = _register_and_login(client, "n3.recipient@example.com")
    outsider_token, outsider_id = _register_and_login(client, "n3.outsider@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega N3")
    for user_id in (proposer_id, recipient_id, outsider_id):
        _add_member(db_session, league_id, user_id)
    athlete = _seed_athlete(db_session, 9801, "Scambio Da Approvare")
    recipient_team_id = _own_athlete_at_slot(client, league_id, recipient_token, 0, athlete)
    client.get(f"/leagues/{league_id}/rosa", headers=_hdr(proposer_token))
    client.get(f"/leagues/{league_id}/rosa", headers=_hdr(outsider_token))
    _set_league_rules(client, league_id, admin_token, require_trade_approval=True)

    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers=_hdr(proposer_token),
        json={
            "recipientTeamId": recipient_team_id,
            "offeredCredits": 20,
            "requestedAthleteIds": [str(athlete.id)],
            "expiresAt": _future_iso(),
        },
    ).json()
    pid = proposal["id"]

    # Finché è solo proposto, l'owner (non parte in causa) non lo vede.
    before = client.get(f"/leagues/{league_id}/mercato/scambi/proposte", headers=_hdr(admin_token))
    assert pid not in [row["id"] for row in before.json()["proposals"]]

    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{pid}/accetta",
        headers=_hdr(recipient_token),
    )
    assert accepted.json()["status"] == "pending_approval"

    listed = client.get(f"/leagues/{league_id}/mercato/scambi/proposte", headers=_hdr(admin_token))
    assert pid in [row["id"] for row in listed.json()["proposals"]]
    detail = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte/{pid}", headers=_hdr(admin_token)
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "pending_approval"

    # Un membro estraneo, non owner, continua a non vedere nulla.
    outsider = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte/{pid}", headers=_hdr(outsider_token)
    )
    assert outsider.status_code == 400
    assert outsider.json()["code"] == "trade_access_forbidden"
    outsider_list = client.get(
        f"/leagues/{league_id}/mercato/scambi/proposte", headers=_hdr(outsider_token)
    )
    assert pid not in [row["id"] for row in outsider_list.json()["proposals"]]

    db_session.expire_all()
    notified = db_session.scalars(
        select(Notification).where(
            Notification.user_id == admin_id,
            Notification.template_key == "mercato.scambio",
        )
    ).all()
    assert len(notified) == 1
    assert "da approvare" in (notified[0].title or "")


def test_member_cannot_release_for_league_exit_but_owner_can(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "n6.admin@example.com")
    member_token, member_id = _register_and_login(client, "n6.member@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega N6")
    _add_member(db_session, league_id, member_id)
    athlete = _seed_athlete(db_session, 9802, "Svincolo Uscita")
    _own_athlete_at_slot(client, league_id, member_token, 0, athlete)

    denied = client.post(
        f"/leagues/{league_id}/mercato/svincolo/0",
        headers=_hdr(member_token),
        json={"reason": "league_exit"},
    )
    assert denied.status_code == 400
    assert denied.json()["code"] == "release_reason_forbidden"
    preview = client.get(
        f"/leagues/{league_id}/mercato/svincolo/0/anteprima",
        headers=_hdr(member_token),
        params={"causa": "league_exit"},
    )
    assert preview.status_code == 400

    voluntary = client.post(
        f"/leagues/{league_id}/mercato/svincolo/0",
        headers=_hdr(member_token),
        json={"reason": "voluntary"},
    )
    assert voluntary.status_code == 200


def test_failed_slot_assignment_leaves_no_partial_write(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    admin_token, _ = _register_and_login(client, "n1.admin@example.com")
    league_id = _create_league(client, admin_token, competition_ids, "Lega N1")
    athlete = _seed_athlete(db_session, 9803, "Troppo Caro")
    team_id = client.get(f"/leagues/{league_id}/rosa", headers=_hdr(admin_token)).json()["id"]

    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers=_hdr(admin_token),
        json={"athleteId": str(athlete.id), "purchaseCredits": 999_999},
    )
    assert response.status_code == 400

    db_session.expire_all()
    slot = db_session.scalar(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == UUID(team_id),
            FantasyRosterSlot.slot_index == 0,
        )
    )
    assert slot is None or slot.athlete_id is None
    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    assert account.balance == 1000
