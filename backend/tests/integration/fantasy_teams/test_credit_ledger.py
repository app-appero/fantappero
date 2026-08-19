"""Integration tests for credit ledger (EP05-02)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import CreditLedgerReason, LeagueAuditAction, LeagueMemberRole
from database.session import create_session_factory
from fantasy_teams.ledger import reconstruct_balance
from fantasy_teams.models import CreditAccount, CreditLedgerEntry, FantasyTeam
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails


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


def _create_league(
    client: TestClient,
    token: str,
    competition_ids: list[str],
    name: str,
) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "seasonYear": 2026,
            "competitionIds": competition_ids,
        },
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


def test_team_creation_seeds_reconstructable_initial_credits(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "cr.owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Crediti")

    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert credits.status_code == 200
    body = credits.json()
    assert body["balance"] == 1000
    assert body["reconstructedBalance"] == 1000
    assert body["version"] == 1

    movements = client.get(
        f"/leagues/{league_id}/crediti/movimenti",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert movements.status_code == 200
    entries = movements.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["reason"] == CreditLedgerReason.INITIAL_ALLOCATION.value
    assert entries[0]["amount"] == 1000

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(body["fantasyTeamId"]))
    )
    assert account is not None
    assert reconstruct_balance(db_session, account.id) == account.balance

    audit = db_session.scalar(
        select(func.count(LeagueAuditEvent.id)).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.CREDIT_ACCOUNT_INITIALIZED,
        )
    )
    assert audit >= 1


def test_admin_can_read_team_credits(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "cr.admin.read@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Read Credits")
    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {token}"},
    )
    team_id = credits.json()["fantasyTeamId"]

    response = client.get(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/crediti",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fantasyTeamId"] == team_id
    assert body["balance"] == credits.json()["balance"]
    assert len(body["entries"]) >= 1

    token, _ = _register_and_login(client, "cr.adj.owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Adj")
    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {token}"},
    )
    team_id = credits.json()["fantasyTeamId"]

    first = client.post(
        f"/leagues/{league_id}/amministrazione/crediti/movimenti",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "fantasyTeamId": team_id,
            "amount": -100,
            "transactionId": "adj-1",
            "note": "Correzione",
        },
    )
    assert first.status_code == 200
    assert first.json()["balance"] == 900
    assert first.json()["version"] == 2

    replay = client.post(
        f"/leagues/{league_id}/amministrazione/crediti/movimenti",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "fantasyTeamId": team_id,
            "amount": -100,
            "transactionId": "adj-1",
            "note": "Correzione",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["balance"] == 900
    assert replay.json()["version"] == 2
    assert len(replay.json()["entries"]) == 2

    overdraw = client.post(
        f"/leagues/{league_id}/amministrazione/crediti/movimenti",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "fantasyTeamId": team_id,
            "amount": -1000,
            "transactionId": "adj-over",
        },
    )
    assert overdraw.status_code == 400
    assert overdraw.json()["code"] == "insufficient_credits"

    entry_count = db_session.scalar(
        select(func.count(CreditLedgerEntry.id)).where(
            CreditLedgerEntry.account_id
            == db_session.scalar(
                select(CreditAccount.id).where(CreditAccount.fantasy_team_id == UUID(team_id))
            )
        )
    )
    assert entry_count == 2


def test_credit_endpoints_require_membership_permissions(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "cr.perm.owner@example.com")
    member_token, member_id = _register_and_login(client, "cr.perm.member@example.com")
    outsider_token, _ = _register_and_login(client, "cr.perm.out@example.com")
    league_id = _create_league(client, owner_token, competition_ids, "Lega Perm Crediti")
    _add_member(db_session, league_id, member_id)

    member_ok = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert member_ok.status_code == 200

    forbidden = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert forbidden.status_code == 403

    member_admin = client.post(
        f"/leagues/{league_id}/amministrazione/crediti/movimenti",
        headers={"Authorization": f"Bearer {member_token}"},
        json={
            "fantasyTeamId": member_ok.json()["fantasyTeamId"],
            "amount": -1,
            "transactionId": "member-adj",
        },
    )
    assert member_admin.status_code == 403


def test_concurrent_adjustments_preserve_valid_balance(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "cr.conc.owner@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Conc Crediti")
    credits = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {token}"},
    )
    team_id = credits.json()["fantasyTeamId"]

    def _adjust(index: int) -> int:
        response = client.post(
            f"/leagues/{league_id}/amministrazione/crediti/movimenti",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "fantasyTeamId": team_id,
                "amount": -100,
                "transactionId": f"conc-{index}",
            },
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(_adjust, range(4)))

    assert statuses.count(200) == 4
    final = client.get(
        f"/leagues/{league_id}/crediti",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert final.status_code == 200
    assert final.json()["balance"] == 600
    assert final.json()["reconstructedBalance"] == 600

    account = db_session.scalar(
        select(CreditAccount).where(CreditAccount.fantasy_team_id == UUID(team_id))
    )
    assert account is not None
    assert account.balance == reconstruct_balance(db_session, account.id)
    assert account.balance >= 0

    teams = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).all()
    assert len(teams) == 1
