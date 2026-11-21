"""Integration tests: listone filtered by the league's chosen competitions (EP11-04b)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

import auth.dependencies as auth_dependencies
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

    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    assert rosa.status_code == 200
    team_id = rosa.json()["id"]

    response = client.put(
        f"/leagues/{league_id}/amministrazione/squadre/{team_id}/slot/0",
        headers={"Authorization": f"Bearer {token}"},
        json={"athleteId": str(athlete.id), "purchaseCredits": 0},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "role_unresolved"


# ── Campionato di ogni voce del listone (filtri «Campionato» e «Squadra», Rosario 21/11) ──


@pytest.fixture
def mvp_competitions(db_session: Session) -> list[Competition]:
    """I cinque campionati del catalogo MVP, in ordine di nome (una lega ne sceglie almeno 3)."""
    rows = db_session.scalars(
        select(Competition)
        .where(Competition.provider_id.in_((39, 140, 135, 78, 61)))
        .order_by(Competition.name.asc())
    ).all()
    assert len(rows) == 5
    return list(rows)


def _sport_season(db_session: Session, *, competition_id: UUID, year: int) -> SportSeason:
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id, SportSeason.year == year
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition_id, year=year)
        db_session.add(season)
        db_session.flush()
    return season


def _seed_club(
    db_session: Session,
    *,
    provider_id: int,
    name: str,
    memberships: list[tuple[UUID, int]],
) -> Club:
    """Club con le sue partecipazioni (campionato, anno): una per ogni stagione indicata."""
    club = Club(provider_id=provider_id, name=name)
    db_session.add(club)
    db_session.flush()
    for competition_id, year in memberships:
        season = _sport_season(db_session, competition_id=competition_id, year=year)
        db_session.add(CompetitionSeasonClub(sport_season_id=season.id, club_id=club.id))
    db_session.commit()
    db_session.refresh(club)
    return club


def _listone_by_athlete(client: TestClient, token: str, league_id: str) -> dict[str, dict]:
    response = client.get(
        f"/leagues/{league_id}/listone",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return {row["athleteId"]: row for row in response.json()}


def _count_request_queries(call) -> tuple[object, int]:
    engine = auth_dependencies._engine
    assert engine is not None
    count = 0

    def _before_cursor_execute(*_args: object) -> None:
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        response = call()
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
    return response, count


def test_listone_entries_carry_the_club_competition(
    client: TestClient, db_session: Session, mvp_competitions: list[Competition]
) -> None:
    token, _ = _register_and_login(client, "listone.competition.a@example.com")
    first, second = mvp_competitions[:2]
    league_id = _create_league(client, token, [str(row.id) for row in mvp_competitions[:3]])

    club_first = _seed_club(
        db_session,
        provider_id=990101,
        name="Club Primo Campionato",
        memberships=[(first.id, SEASON_YEAR)],
    )
    club_second = _seed_club(
        db_session,
        provider_id=990102,
        name="Club Secondo Campionato",
        memberships=[(second.id, SEASON_YEAR)],
    )
    in_first = _seed_athlete(
        db_session, provider_id=880101, name="Giocatore Primo", club_id=club_first.id
    )
    in_second = _seed_athlete(
        db_session, provider_id=880102, name="Giocatore Secondo", club_id=club_second.id
    )
    without_club = _seed_athlete(
        db_session, provider_id=880103, name="Giocatore Senza Club Campionato", club_id=None
    )

    rows = _listone_by_athlete(client, token, league_id)

    assert rows[str(in_first.id)]["clubName"] == "Club Primo Campionato"
    assert rows[str(in_first.id)]["competitionId"] == str(first.id)
    assert rows[str(in_first.id)]["competitionName"] == first.name
    assert rows[str(in_second.id)]["competitionId"] == str(second.id)
    assert rows[str(in_second.id)]["competitionName"] == second.name
    # Senza club non c'è campionato: la voce resta nel listone, con i campi nulli.
    assert rows[str(without_club.id)]["competitionId"] is None
    assert rows[str(without_club.id)]["competitionName"] is None


def test_listone_competition_is_the_one_of_the_league_season(
    client: TestClient, db_session: Session, mvp_competitions: list[Competition]
) -> None:
    """Conta la stagione della lega, e solo fra i campionati scelti dalla lega."""
    token, _ = _register_and_login(client, "listone.competition.b@example.com")
    first, second = mvp_competitions[:2]
    not_chosen = mvp_competitions[4]
    league_id = _create_league(client, token, [str(row.id) for row in mvp_competitions[:3]])

    # Promosso: l'anno prima era in un campionato non scelto, quest'anno è nel secondo.
    promoted = _seed_club(
        db_session,
        provider_id=990111,
        name="Club Promosso",
        memberships=[(not_chosen.id, SEASON_YEAR - 1), (second.id, SEASON_YEAR)],
    )
    # Anche in una coppa non scelta dalla lega (prima per nome): conta solo il campionato.
    cup = Competition(provider_id=990199, name="AAA Coppa Non Scelta", country="ZZ")
    db_session.add(cup)
    db_session.commit()
    db_session.refresh(cup)
    with_cup = _seed_club(
        db_session,
        provider_id=990112,
        name="Club Con Coppa",
        memberships=[(cup.id, SEASON_YEAR), (first.id, SEASON_YEAR)],
    )
    promoted_athlete = _seed_athlete(
        db_session, provider_id=880111, name="Giocatore Promosso", club_id=promoted.id
    )
    cup_athlete = _seed_athlete(
        db_session, provider_id=880112, name="Giocatore Con Coppa", club_id=with_cup.id
    )

    rows = _listone_by_athlete(client, token, league_id)

    assert rows[str(promoted_athlete.id)]["competitionId"] == str(second.id)
    assert rows[str(promoted_athlete.id)]["competitionName"] == second.name
    assert rows[str(cup_athlete.id)]["competitionId"] == str(first.id)
    assert rows[str(cup_athlete.id)]["competitionName"] == first.name


def test_listone_competition_lookup_does_not_grow_with_clubs(
    client: TestClient, db_session: Session, mvp_competitions: list[Competition]
) -> None:
    """Il campionato si legge con una query sola per tutto il listone (niente N+1)."""
    token, _ = _register_and_login(client, "listone.competition.c@example.com")
    league_competitions = mvp_competitions[:3]
    league_id = _create_league(client, token, [str(row.id) for row in league_competitions])

    def seed_clubs(offset: int, count: int) -> None:
        for index in range(count):
            competition = league_competitions[index % len(league_competitions)]
            club = _seed_club(
                db_session,
                provider_id=990200 + offset + index,
                name=f"Club Budget {offset + index}",
                memberships=[(competition.id, SEASON_YEAR)],
            )
            _seed_athlete(
                db_session,
                provider_id=880200 + offset + index,
                name=f"Giocatore Budget {offset + index}",
                club_id=club.id,
            )

    def get_listone():
        return client.get(
            f"/leagues/{league_id}/listone",
            headers={"Authorization": f"Bearer {token}"},
        )

    seed_clubs(0, 2)
    get_listone()  # riscaldamento: cache di autenticazione e impostazioni
    first_response, before = _count_request_queries(get_listone)
    seed_clubs(10, 6)
    second_response, after = _count_request_queries(get_listone)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    budget_rows = [
        row for row in second_response.json() if row["canonicalName"].startswith("Giocatore Budget")
    ]
    assert len(budget_rows) == 8
    assert all(row["competitionId"] for row in budget_rows)
    assert after == before


def test_role_override_responses_keep_the_competition(
    client: TestClient, db_session: Session, mvp_competitions: list[Competition]
) -> None:
    """La voce restituita dall'override sostituisce quella del listone: deve avere il campionato."""
    token, _ = _register_and_login(client, "listone.competition.d@example.com")
    first = mvp_competitions[0]
    league_id = _create_league(client, token, [str(row.id) for row in mvp_competitions[:3]])
    club = _seed_club(
        db_session,
        provider_id=990301,
        name="Club Override Campionato",
        memberships=[(first.id, SEASON_YEAR)],
    )
    athlete = _seed_athlete(
        db_session, provider_id=880301, name="Giocatore Override Campionato", club_id=club.id
    )

    set_response = client.put(
        f"/leagues/{league_id}/amministrazione/listone/{athlete.id}/ruolo",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "C"},
    )
    assert set_response.status_code == 200
    assert set_response.json()["competitionId"] == str(first.id)
    assert set_response.json()["competitionName"] == first.name

    clear_response = client.delete(
        f"/leagues/{league_id}/amministrazione/listone/{athlete.id}/ruolo",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["competitionId"] == str(first.id)
    assert clear_response.json()["competitionName"] == first.name
