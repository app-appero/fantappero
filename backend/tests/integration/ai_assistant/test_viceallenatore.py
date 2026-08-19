"""Integration tests for the Viceallenatore advisory service (EP10-02)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_assistant.models import AiInteraction
from ai_assistant.viceallenatore_service import ViceallenatoreService
from auth.models.user import User
from authorization.context import LeagueAccess
from database.enums import (
    FantasyModule,
    FantasyRole,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueMemberRole,
    LineupSlotKind,
)
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound
from leagues.models.competition import Competition
from leagues.models.league import League
from mail.capture import get_captured_emails
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


def test_suggests_bench_replacement_for_injured_starter(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "vice-basic@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Vice"))
    league = db_session.get(League, league_id)
    user = db_session.get(User, user_id)
    team = db_session.scalars(select(FantasyTeam).where(FantasyTeam.league_id == league_id)).one()

    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=league_id,
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now - timedelta(days=1),
        window_end_at=now + timedelta(days=2),
        cutoff_at=now + timedelta(hours=2),
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now,
    )
    db_session.add(fantasy_round)
    db_session.flush()

    starter = Athlete(provider_id=940001, canonical_name="Titolare Infortunato", injured=True)
    bench = Athlete(provider_id=940002, canonical_name="Panchinaro Pronto", injured=False)
    db_session.add_all([starter, bench])
    db_session.flush()

    submission = LineupSubmission(
        league_id=league_id,
        round_id=fantasy_round.id,
        fantasy_team_id=team.id,
        module=FantasyModule.M442,
        submitted_at=now,
        submitted_by_user_id=user_id,
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add_all(
        [
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=starter.id,
                slot_kind=LineupSlotKind.STARTER,
                role=FantasyRole.A,
                sort_order=0,
            ),
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=bench.id,
                slot_kind=LineupSlotKind.BENCH,
                role=FantasyRole.A,
                sort_order=0,
            ),
        ]
    )
    db_session.commit()

    league_access = LeagueAccess(league=league, user=user, membership_role=LeagueMemberRole.OWNER)
    advice = ViceallenatoreService(db_session).suggest(league_access, fantasy_round.id)

    assert len(advice.suggestions) == 1
    suggestion = advice.suggestions[0]
    assert suggestion.starter_athlete_id == starter.id
    assert suggestion.bench_athlete_id == bench.id
    assert advice.interaction_id is not None

    interaction = db_session.get(AiInteraction, advice.interaction_id)
    assert interaction is not None
    assert interaction.feature.value == "viceallenatore"


def test_no_suggestions_when_no_starter_is_injured(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token, user_id = _register_and_login(client, "vice-healthy@example.com")
    league_id = UUID(_create_league(client, token, competition_ids, "Lega Vice Sana"))
    league = db_session.get(League, league_id)
    user = db_session.get(User, user_id)
    team = db_session.scalars(select(FantasyTeam).where(FantasyTeam.league_id == league_id)).one()

    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=league_id,
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now - timedelta(days=1),
        window_end_at=now + timedelta(days=2),
        cutoff_at=now + timedelta(hours=2),
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now,
    )
    db_session.add(fantasy_round)
    db_session.flush()

    starter = Athlete(provider_id=940003, canonical_name="Titolare Ok", injured=False)
    db_session.add(starter)
    db_session.flush()

    submission = LineupSubmission(
        league_id=league_id,
        round_id=fantasy_round.id,
        fantasy_team_id=team.id,
        module=FantasyModule.M442,
        submitted_at=now,
        submitted_by_user_id=user_id,
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(
        LineupPlayer(
            submission_id=submission.id,
            athlete_id=starter.id,
            slot_kind=LineupSlotKind.STARTER,
            role=FantasyRole.A,
            sort_order=0,
        )
    )
    db_session.commit()

    league_access = LeagueAccess(league=league, user=user, membership_role=LeagueMemberRole.OWNER)
    advice = ViceallenatoreService(db_session).suggest(league_access, fantasy_round.id)

    assert advice.suggestions == ()
    assert advice.message == "Nessun cambio consigliato."
