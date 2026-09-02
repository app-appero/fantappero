"""Integration tests for market/trade event notifications (EP09-03)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.models.user import User
from authorization.context import LeagueAccess
from database.enums import (
    LeagueMemberRole,
    MarketSessionKind,
    MarketSessionStatus,
    NotificationCategory,
)
from fantasy_teams.factory import ensure_team_for_membership
from fantasy_teams.models import FantasyTeam
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from market.models import MarketBid, MarketSession, TradeProposal
from market.service import MarketService
from market.trade_service import TradeService
from notifications.models import Notification
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


def _second_team(db_session: Session, league_id: UUID, user_id: UUID) -> FantasyTeam:
    membership = LeagueMembership(
        league_id=league_id, user_id=user_id, role=LeagueMemberRole.MEMBER
    )
    db_session.add(membership)
    db_session.commit()
    team, _ = ensure_team_for_membership(db_session, membership, name="Squadra Sfidante")
    db_session.commit()
    return team


def test_market_resolution_notifies_winner_and_loser(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, owner_id = _register_and_login(client, "market-evt-owner@example.com")
    _, challenger_id = _register_and_login(client, "market-evt-challenger@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Eventi Mercato"))

    league = db_session.get(League, league_id)
    owner_user = db_session.get(User, owner_id)
    owner_team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == league_id)
    ).one()
    challenger_team = _second_team(db_session, league_id, challenger_id)

    athlete = Athlete(provider_id=990001, canonical_name="Bomber Notifiche")
    db_session.add(athlete)
    db_session.commit()

    now = datetime.now(UTC)
    market_session = MarketSession(
        league_id=league_id,
        kind=MarketSessionKind.INITIAL_AUCTION,
        status=MarketSessionStatus.CLOSED,
        opens_at=now - timedelta(hours=2),
        closes_at=now - timedelta(minutes=1),
        created_by=owner_id,
    )
    db_session.add(market_session)
    db_session.flush()
    db_session.add_all(
        [
            MarketBid(
                session_id=market_session.id,
                fantasy_team_id=owner_team.id,
                athlete_id=athlete.id,
                amount_credits=50,
            ),
            MarketBid(
                session_id=market_session.id,
                fantasy_team_id=challenger_team.id,
                athlete_id=athlete.id,
                amount_credits=10,
            ),
        ]
    )
    db_session.commit()

    league_access = LeagueAccess(
        league=league, user=owner_user, membership_role=LeagueMemberRole.OWNER
    )
    MarketService(db_session).resolve_session(league_access, market_session.id)

    winner_notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == owner_id,
            Notification.category == NotificationCategory.MERCATO,
        )
    )
    assert winner_notification is not None
    assert "aggiudicat" in winner_notification.title.lower()

    loser_notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == challenger_id,
            Notification.category == NotificationCategory.MERCATO,
        )
    )
    assert loser_notification is not None
    assert "non aggiudicata" in loser_notification.title.lower()


def test_trade_proposal_notifies_recipient(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, proposer_id = _register_and_login(client, "trade-evt-new-proposer@example.com")
    _, recipient_id = _register_and_login(client, "trade-evt-new-recipient@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Nuova Proposta"))

    league = db_session.get(League, league_id)
    proposer_user = db_session.get(User, proposer_id)
    proposer_team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == league_id)
    ).one()
    recipient_team = _second_team(db_session, league_id, recipient_id)

    league_access = LeagueAccess(
        league=league, user=proposer_user, membership_role=LeagueMemberRole.OWNER
    )
    from market.trade_schemas import CreateTradeProposalRequest

    TradeService(db_session).create_proposal(
        league_access,
        CreateTradeProposalRequest(
            recipientTeamId=str(recipient_team.id),
            offeredAthleteIds=[],
            requestedAthleteIds=[],
            offeredCredits=5,
            requestedCredits=0,
            expiresAt=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
        ),
    )

    notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == recipient_id,
            Notification.category == NotificationCategory.MERCATO,
        )
    )
    assert notification is not None
    assert notification.title == "Nuova proposta di scambio"

    # Proposer must not get a self-notification on create.
    proposer_notes = db_session.scalars(
        select(Notification).where(
            Notification.user_id == proposer_id,
            Notification.category == NotificationCategory.MERCATO,
        )
    ).all()
    assert proposer_notes == []


def test_trade_rejection_notifies_proposer(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, proposer_id = _register_and_login(client, "trade-evt-proposer@example.com")
    _, recipient_id = _register_and_login(client, "trade-evt-recipient@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Eventi Scambio"))

    league = db_session.get(League, league_id)
    proposer_team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == league_id)
    ).one()
    recipient_team = _second_team(db_session, league_id, recipient_id)
    recipient_user = db_session.get(User, recipient_id)

    proposal = TradeProposal(
        league_id=league_id,
        proposer_team_id=proposer_team.id,
        recipient_team_id=recipient_team.id,
        offered_athlete_ids=[],
        requested_athlete_ids=[],
        offered_credits=10,
        requested_credits=0,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    db_session.add(proposal)
    db_session.commit()

    league_access = LeagueAccess(
        league=league, user=recipient_user, membership_role=LeagueMemberRole.MEMBER
    )
    TradeService(db_session).reject_proposal(league_access, proposal.id)

    notification = db_session.scalar(
        select(Notification).where(
            Notification.user_id == proposer_id,
            Notification.category == NotificationCategory.MERCATO,
        )
    )
    assert notification is not None
    assert notification.title == "Scambio rifiutato"

    # Idempotent replay (e.g. a retried request) must not duplicate the notification.
    again = db_session.scalars(
        select(Notification).where(
            Notification.user_id == proposer_id,
            Notification.category == NotificationCategory.MERCATO,
        )
    ).all()
    assert len(again) == 1
