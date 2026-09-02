"""Integration tests: listone filtered by the league's chosen competitions (EP11-04b)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole
from database.session import create_session_factory
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

SEASON_YEAR = 2026


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
def chosen_competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    assert len(rows) >= 3
    return [str(row.id) for row in rows[:3]]


def _create_league(client: TestClient, token: str, competition_ids: list[str]) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Lega Filtro Listone",
            "seasonYear": SEASON_YEAR,
            "competitionIds": competition_ids,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_club_in_competition(
    db_session: Session, *, competition_id: UUID, provider_id: int
) -> Club:
    club = Club(provider_id=provider_id, name=f"Club {provider_id}")
    db_session.add(club)
    db_session.flush()
    season = SportSeason(competition_id=competition_id, year=SEASON_YEAR)
    db_session.add(season)
    db_session.flush()
    db_session.add(CompetitionSeasonClub(sport_season_id=season.id, club_id=club.id))
    db_session.commit()
    db_session.refresh(club)
    return club


def _seed_athlete(
    db_session: Session,
    *,
    provider_id: int,
    name: str,
    club_id: UUID | None,
    role: FantasyRole = FantasyRole.A,
) -> Athlete:
    athlete = Athlete(provider_id=provider_id, canonical_name=name)
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=SEASON_YEAR,
            role=role,
            mapping_version="v1.0.0",
            provider_position_raw=role.value,
            club_id=club_id,
        )
    )
    db_session.commit()
    db_session.refresh(athlete)
    return athlete


def test_listone_shows_athlete_in_chosen_competition(
    client: TestClient, db_session: Session, chosen_competition_ids: list[str]
) -> None:
    token, _ = _register_and_login(client, "listone.filter.a@example.com")
    league_id = _create_league(client, token, chosen_competition_ids)

    club = _seed_club_in_competition(
        db_session, competition_id=UUID(chosen_competition_ids[0]), provider_id=990001
    )
    athlete = _seed_athlete(
        db_session, provider_id=880001, name="Giocatore In Campionato", club_id=club.id
    )

    response = client.get(
        f"/leagues/{league_id}/listone",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    athlete_ids = {row["athleteId"] for row in response.json()}
    assert str(athlete.id) in athlete_ids


def test_listone_hides_athlete_outside_chosen_competitions(
    client: TestClient, db_session: Session, chosen_competition_ids: list[str]
) -> None:
    token, _ = _register_and_login(client, "listone.filter.b@example.com")
    league_id = _create_league(client, token, chosen_competition_ids)

    other_competition = Competition(provider_id=990099, name="Campionato Escluso", country="XX")
    db_session.add(other_competition)
    db_session.commit()
    db_session.refresh(other_competition)

    club = _seed_club_in_competition(
        db_session, competition_id=other_competition.id, provider_id=990002
    )
    athlete = _seed_athlete(
        db_session, provider_id=880002, name="Giocatore Fuori Campionato", club_id=club.id
    )

    response = client.get(
        f"/leagues/{league_id}/listone",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    athlete_ids = {row["athleteId"] for row in response.json()}
    assert str(athlete.id) not in athlete_ids


def test_listone_shows_athlete_with_unresolved_club(
    client: TestClient, db_session: Session, chosen_competition_ids: list[str]
) -> None:
    """A RoleAssignment without club_id (data-quality gap) is never hidden by the filter."""
    token, _ = _register_and_login(client, "listone.filter.c@example.com")
    league_id = _create_league(client, token, chosen_competition_ids)

    athlete = _seed_athlete(
        db_session, provider_id=880003, name="Giocatore Senza Club", club_id=None
    )

    response = client.get(
        f"/leagues/{league_id}/listone",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    athlete_ids = {row["athleteId"] for row in response.json()}
    assert str(athlete.id) in athlete_ids


def test_new_assignment_rejects_athlete_outside_competitions(
    client: TestClient, db_session: Session, chosen_competition_ids: list[str]
) -> None:
    """assert_assignment_respects_role_quota blocks picking an athlete outside the league's
    competitions, but never touches roles of athletes already on a roster (see
    composition_service.py:229, deliberately left unfiltered)."""
    token, _ = _register_and_login(client, "listone.filter.d@example.com")
    league_id = _create_league(client, token, chosen_competition_ids)

    other_competition = Competition(
        provider_id=990098, name="Altro Campionato Escluso", country="YY"
    )
    db_session.add(other_competition)
    db_session.commit()
    db_session.refresh(other_competition)

    club = _seed_club_in_competition(
        db_session, competition_id=other_competition.id, provider_id=990003
    )
    athlete = _seed_athlete(
        db_session, provider_id=880004, name="Giocatore Non Assegnabile", club_id=club.id
    )

    rosa = client.get(
        f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"}
    )
    assert rosa.status_code == 200
    team_id = rosa.json()["id"]

    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 0},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "role_unresolved"
