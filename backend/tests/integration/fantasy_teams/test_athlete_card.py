"""Scheda calciatore: dati provider già salvati e rosa della lega corrente."""

from __future__ import annotations

import re
from datetime import date
from uuid import UUID, uuid4

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
from sports_data.catalog.models import Club, SportSeason
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete, SquadMembership, Transfer


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


def test_athlete_card_returns_provider_profile_and_league_assignment(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _user_id = _register_and_login(client, "card.owner@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Lega Scheda", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201
    league_id = created.json()["id"]

    club = Club(provider_id=880441, name="Nice")
    previous = Club(provider_id=880440, name="Lille")
    db_session.add_all([club, previous])
    db_session.flush()
    season = SportSeason(competition_id=UUID(competition_ids[0]), year=2099, is_current=False)
    db_session.add(season)
    db_session.flush()

    owned = Athlete(
        provider_id=880442,
        canonical_name="K. Thuram",
        first_name="Khéphren",
        last_name="Thuram",
        nationality="France",
        birth_date=date(2001, 3, 26),
        age=25,
        height="192 cm",
        weight="78 kg",
        injured=False,
        photo_url="https://example.test/thuram.png",
    )
    free = Athlete(provider_id=880443, canonical_name="Libero Uno")
    db_session.add_all([owned, free])
    db_session.flush()
    db_session.add(
        SquadMembership(
            athlete_id=owned.id,
            club_id=club.id,
            sport_season_id=season.id,
            shirt_number=19,
            provider_position_raw="Midfielder",
            is_active=True,
            source="squads",
        )
    )
    db_session.add(
        Transfer(
            athlete_id=owned.id,
            transfer_date=date(2024, 7, 1),
            from_club_id=previous.id,
            to_club_id=club.id,
            transfer_type="Loan",
            provider_key="athlete-card-thuram-2024",
        )
    )
    db_session.add(
        RoleAssignment(
            athlete_id=owned.id,
            season_year=2026,
            role=FantasyRole.C,
            mapping_version="v1.0.0",
            provider_position_raw="Midfielder",
        )
    )
    db_session.commit()

    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    assert rosa.status_code == 200
    team_id = rosa.json()["id"]
    team_name = rosa.json()["name"]
    assigned = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(owned.id), "purchaseCredits": 22},
    )
    assert assigned.status_code == 200

    card = client.get(
        f"/leagues/{league_id}/calciatori/{owned.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert card.status_code == 200
    body = card.json()
    assert body["canonicalName"] == "K. Thuram"
    assert body["photoUrl"] == "https://example.test/thuram.png"
    assert body["nationality"] == "France"
    assert body["clubName"] == "Nice"
    assert body["shirtNumber"] == 19
    assert body["role"] == "C"
    assert body["assignment"]["teamName"] == team_name
    assert body["assignment"]["purchaseCredits"] == 22
    assert body["assignment"]["slotIndex"] == 0
    assert body["seasons"][0]["clubName"] == "Nice"
    assert body["seasons"][0]["seasonYear"] == 2099
    assert body["transfers"][0]["fromClubName"] == "Lille"
    assert body["transfers"][0]["toClubName"] == "Nice"
    assert body["transfers"][0]["transferType"] == "Loan"

    free_card = client.get(
        f"/leagues/{league_id}/calciatori/{free.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert free_card.status_code == 200
    assert free_card.json()["assignment"] is None
    assert free_card.json()["canonicalName"] == "Libero Uno"

    missing = client.get(
        f"/leagues/{league_id}/calciatori/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "athlete_not_found"


def test_athlete_card_requires_league_membership(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    owner_token, _ = _register_and_login(client, "card.private.owner@example.com")
    outsider_token, outsider_id = _register_and_login(client, "card.outsider@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"name": "Lega Chiusa Scheda", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201
    league_id = created.json()["id"]
    athlete = Athlete(provider_id=880444, canonical_name="Privato")
    db_session.add(athlete)
    db_session.commit()

    denied = client.get(
        f"/leagues/{league_id}/calciatori/{athlete.id}",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert denied.status_code in {403, 404}
    assert outsider_id
    membership = db_session.scalar(
        select(LeagueMembership).where(LeagueMembership.user_id == outsider_id)
    )
    assert membership is None or membership.role != LeagueMemberRole.OWNER
