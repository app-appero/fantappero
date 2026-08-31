"""Un turno esiste solo se i fantallenatori possono schierare la formazione."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueMemberRole, LeagueState
from database.session import create_session_factory
from fantasy_teams.models import FantasyRosterSlot
from fantasy_turns.models import FantasyRound
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_competition import LeagueCompetition
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

# Rosa minima che copre gli 11 titolari con un 4-4-2: il test lavora su rose
# piccole ma complete, non su rose regolamentari da 35.
_SQUAD = ((FantasyRole.P, 1), (FantasyRole.D, 4), (FantasyRole.C, 4), (FantasyRole.A, 2))


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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


def _season_for(db_session: Session, competition_id: UUID) -> SportSeason:
    season = db_session.scalar(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id,
            SportSeason.year == 2026,
        )
    )
    if season is None:
        season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()
    return season


def _make_club(
    db_session: Session, provider_id: int, name: str, *, season: SportSeason
) -> Club:
    club = Club(provider_id=provider_id, name=name)
    db_session.add(club)
    db_session.flush()
    db_session.add(CompetitionSeasonClub(sport_season_id=season.id, club_id=club.id))
    db_session.flush()
    return club


def _stock_team(
    db_session: Session,
    *,
    team_id: UUID,
    league_id: UUID,
    club: Club,
    provider_id_start: int,
) -> None:
    """Assegna una formazione completa (tutta di un club) agli slot già creati.

    `ensure_team_for_membership` crea la rosa con gli slot vuoti: qui vanno
    popolati, non inseriti da capo.
    """
    slots = list(
        db_session.scalars(
            select(FantasyRosterSlot)
            .where(FantasyRosterSlot.fantasy_team_id == team_id)
            .order_by(FantasyRosterSlot.slot_index.asc())
        ).all()
    )
    provider_id = provider_id_start
    cursor = 0
    for role, count in _SQUAD:
        for _ in range(count):
            athlete = Athlete(provider_id=provider_id, canonical_name=f"Player {provider_id}")
            db_session.add(athlete)
            db_session.flush()
            db_session.add(
                RoleAssignment(
                    athlete_id=athlete.id,
                    season_year=2026,
                    role=role,
                    club_id=club.id,
                    mapping_version="v1.0.0",
                    provider_position_raw=role.value,
                )
            )
            slots[cursor].athlete_id = athlete.id
            provider_id += 1
            cursor += 1
    db_session.flush()


def _fixture(
    db_session: Session,
    *,
    season: SportSeason,
    home: Club,
    away: Club,
    kickoff: datetime,
    provider_id: int,
) -> None:
    db_session.add(
        Fixture(
            provider_id=provider_id,
            sport_season_id=season.id,
            home_club_id=home.id,
            away_club_id=away.id,
            kickoff_at=kickoff,
            status_short="NS",
        )
    )
    db_session.flush()


def _build_league(
    client: TestClient, db_session: Session, *, prefix: str, offset: int
) -> tuple[str, str, list[Club]]:
    """Lega attiva con due squadre, ognuna con una rosa completa di un club."""
    token, owner_id = _register_and_login(client, f"{prefix}.owner@example.com")
    _, rival_id = _register_and_login(client, f"{prefix}.rival@example.com")

    competition = db_session.scalars(select(Competition)).first()
    assert competition is not None
    season = _season_for(db_session, competition.id)

    league = League(name=f"Lega Copertura {prefix}", season_year=2026, state=LeagueState.ACTIVE)
    db_session.add(league)
    db_session.flush()
    db_session.add(LeagueRules(league_id=league.id, min_fixtures_per_round=10))
    db_session.add(LeagueCompetition(league_id=league.id, competition_id=competition.id))

    memberships = []
    for user_id, role in ((owner_id, LeagueMemberRole.OWNER), (rival_id, LeagueMemberRole.MEMBER)):
        membership = LeagueMembership(league_id=league.id, user_id=user_id, role=role)
        db_session.add(membership)
        db_session.flush()
        memberships.append(membership)

    clubs = [
        _make_club(db_session, offset + 1, "Club Casa", season=season),
        _make_club(db_session, offset + 2, "Club Ospite", season=season),
    ]
    from fantasy_teams.factory import ensure_team_for_membership

    for index, membership in enumerate(memberships):
        team, _ = ensure_team_for_membership(
            db_session, membership, name=f"Squadra {index + 1}", roster_size=35
        )
        _stock_team(
            db_session,
            team_id=team.id,
            league_id=league.id,
            club=clubs[index],
            provider_id_start=offset + 1_000 + index * 100,
        )

    # Finestra A (14-17 ago): giocano entrambi i club → copertura piena.
    _fixture(
        db_session,
        season=season,
        home=clubs[0],
        away=clubs[1],
        kickoff=datetime(2026, 8, 15, 15, 0, tzinfo=UTC),
        provider_id=offset + 5_001,
    )
    # Serve superare anche il pre-filtro sul numero minimo di partite.
    filler = [_make_club(db_session, offset + 100 + i, f"Filler {i}", season=season) for i in range(20)]
    for index in range(10):
        _fixture(
            db_session,
            season=season,
            home=filler[index * 2],
            away=filler[index * 2 + 1],
            kickoff=datetime(2026, 8, 15, 18, 0, tzinfo=UTC) + timedelta(minutes=index),
            provider_id=offset + 5_100 + index,
        )

    # Finestra B (21-24 ago): giocano solo i club filler, nessun giocatore in
    # rosa scende in campo → copertura zero per entrambe le squadre.
    for index in range(11):
        _fixture(
            db_session,
            season=season,
            home=filler[index % 10 * 2],
            away=filler[index % 10 * 2 + 1],
            kickoff=datetime(2026, 8, 22, 15, 0, tzinfo=UTC) + timedelta(minutes=index),
            provider_id=offset + 6_100 + index,
        )

    db_session.commit()
    return str(league.id), token, clubs


def test_only_windows_where_everyone_can_field_a_lineup_become_turns(
    client: TestClient,
    db_session: Session,
) -> None:
    league_id, token, _ = _build_league(
        client, db_session, prefix="coverage", offset=800_000
    )

    covered = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert covered.status_code == 201

    # Stessa lega, finestra in cui nessun giocatore in rosa gioca: niente turno.
    uncovered = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-22"},
    )
    assert uncovered.status_code == 400
    assert uncovered.json()["code"] == "turn_coverage_not_met"

    rounds = db_session.scalars(
        select(FantasyRound).where(FantasyRound.league_id == UUID(league_id))
    ).all()
    assert len(rounds) == 1
    assert rounds[0].window_start_at < datetime(2026, 8, 18, tzinfo=UTC)


def test_a_league_without_rosters_generates_no_turns(
    client: TestClient,
    db_session: Session,
) -> None:
    """Niente turni prima dell'asta: senza rose non si schiera nulla."""
    league_id, token, _ = _build_league(
        client, db_session, prefix="norosters", offset=830_000
    )

    db_session.execute(
        FantasyRosterSlot.__table__.delete().where(
            FantasyRosterSlot.league_id == UUID(league_id)
        )
    )
    db_session.commit()

    response = client.post(
        f"/leagues/{league_id}/turni",
        headers={"Authorization": f"Bearer {token}"},
        json={"kind": "weekend", "anchorDate": "2026-08-15"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "turn_coverage_not_met"

    rounds = db_session.scalars(
        select(FantasyRound).where(FantasyRound.league_id == UUID(league_id))
    ).all()
    assert rounds == []

