"""Dettaglio partita live: formazioni, cronologia e stato feed (EP13-P04)."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyTurnKind, FantasyTurnStatus
from database.session import create_session_factory
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import (
    Fixture,
    MatchEvent,
    OfficialLineup,
    OfficialLineupEntry,
)
from sports_data.roster.models import Athlete


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _register_and_login(client: TestClient, email: str) -> str:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    return login.json()["accessToken"]


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


def _season(db_session: Session, competition_id: UUID) -> SportSeason:
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id, SportSeason.year == 2026
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()
    return season


def _build_live_fixture(
    db_session: Session,
    *,
    league_id: str,
    competition_id: UUID,
    provider_seed: int,
) -> tuple[FantasyRound, Fixture, Club, Club]:
    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now - timedelta(days=1),
        window_end_at=now + timedelta(days=1),
        cutoff_at=now - timedelta(minutes=30),
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now - timedelta(days=1),
    )
    db_session.add(fantasy_round)
    db_session.flush()

    home = Club(
        provider_id=provider_seed + 1,
        name="Roma FC",
        logo_url="https://media.api-sports.io/football/teams/home.png",
    )
    away = Club(provider_id=provider_seed + 2, name="Milan FC")
    db_session.add_all([home, away])
    db_session.flush()

    season = _season(db_session, competition_id)
    fixture = Fixture(
        provider_id=provider_seed + 50,
        sport_season_id=season.id,
        home_club_id=home.id,
        away_club_id=away.id,
        kickoff_at=now - timedelta(minutes=40),
        status_short="2H",
        status_elapsed=63,
        home_goals=2,
        away_goals=1,
        venue_name="Stadio Olimpico",
        venue_city="Roma",
        referee="M. Rossi",
    )
    db_session.add(fixture)
    db_session.flush()
    db_session.add(
        FantasyRoundFixture(
            round_id=fantasy_round.id,
            league_id=UUID(league_id),
            fixture_id=fixture.id,
            observed_kickoff_at=fixture.kickoff_at,
        )
    )
    return fantasy_round, fixture, home, away


def test_fixture_detail_exposes_lineups_and_ordered_timeline(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token = _register_and_login(client, "live-detail@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Dettaglio Live")
    fantasy_round, fixture, home, away = _build_live_fixture(
        db_session,
        league_id=league_id,
        competition_id=UUID(competition_ids[0]),
        provider_seed=970000,
    )

    scorer = Athlete(
        provider_id=970101,
        canonical_name="Marco Rossi",
        photo_url="https://media.api-sports.io/football/players/970101.png",
    )
    assister = Athlete(provider_id=970102, canonical_name="Luca Bianchi")
    benched = Athlete(provider_id=970103, canonical_name="Paolo Verdi")
    db_session.add_all([scorer, assister, benched])
    db_session.flush()

    lineup = OfficialLineup(
        fixture_id=fixture.id, club_id=home.id, formation="4-3-3", coach_name="J. Mourinho"
    )
    db_session.add(lineup)
    db_session.flush()
    db_session.add_all(
        [
            OfficialLineupEntry(
                lineup_id=lineup.id,
                athlete_id=scorer.id,
                athlete_provider_id=scorer.provider_id,
                is_starter=True,
                shirt_number=10,
                position_raw="F",
                sort_order=1,
            ),
            OfficialLineupEntry(
                lineup_id=lineup.id,
                athlete_id=benched.id,
                athlete_provider_id=benched.provider_id,
                is_starter=False,
                shirt_number=23,
                position_raw="M",
                sort_order=2,
            ),
        ]
    )

    # Fuori ordine di proposito, più un evento ritrattato.
    db_session.add_all(
        [
            MatchEvent(
                provider_event_key="ev-late",
                fixture_id=fixture.id,
                athlete_id=scorer.id,
                club_id=home.id,
                event_type="Goal",
                event_detail="Normal Goal",
                scoring_kind="goal",
                minute_elapsed=63,
            ),
            MatchEvent(
                provider_event_key="ev-early",
                fixture_id=fixture.id,
                athlete_id=scorer.id,
                related_athlete_id=assister.id,
                club_id=home.id,
                event_type="Goal",
                event_detail="Normal Goal",
                scoring_kind="goal",
                minute_elapsed=12,
            ),
            MatchEvent(
                provider_event_key="ev-retracted",
                fixture_id=fixture.id,
                athlete_id=scorer.id,
                club_id=home.id,
                event_type="Goal",
                event_detail="Normal Goal",
                scoring_kind="goal",
                minute_elapsed=30,
                is_active=False,
            ),
            # Stesso gol reale del provider (riga grezza) e la sua copia
            # normalizzata usata per il fantavoto: la copia non deve comparire
            # una seconda volta in cronologia (EP13-P04-ter).
            MatchEvent(
                provider_event_key="ev-dup-raw|primary",
                fixture_id=fixture.id,
                athlete_id=scorer.id,
                club_id=home.id,
                event_type="Goal",
                event_detail="Normal Goal",
                minute_elapsed=77,
                sources=["events"],
            ),
            MatchEvent(
                provider_event_key="ev-dup-raw|goal",
                fixture_id=fixture.id,
                athlete_id=scorer.id,
                club_id=home.id,
                event_type="Goal",
                event_detail="Normal Goal",
                scoring_kind="goal",
                minute_elapsed=77,
                sources=["events"],
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/partite/{fixture.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["homeClubId"] == str(home.id)
    assert body["awayClubId"] == str(away.id)
    assert body["homeClubName"] == "Roma FC"
    assert body["awayClubName"] == "Milan FC"
    assert body["homeGoals"] == 2
    assert body["statusShort"] == "2H"
    assert body["statusElapsed"] == 63
    assert body["venueName"] == "Stadio Olimpico"
    assert body["venueCity"] == "Roma"
    assert body["referee"] == "M. Rossi"
    assert body["homeClubLogoUrl"] == "https://media.api-sports.io/football/teams/home.png"
    # Il logo ospite non è mai stato sincronizzato: assente, non un placeholder.
    assert body["awayClubLogoUrl"] is None

    assert body["homeLineup"]["formation"] == "4-3-3"
    assert body["homeLineup"]["coachName"] == "J. Mourinho"
    assert [p["name"] for p in body["homeLineup"]["starters"]] == ["Marco Rossi"]
    assert body["homeLineup"]["starters"][0]["photoUrl"] == (
        "https://media.api-sports.io/football/players/970101.png"
    )
    # Il panchinaro non ha mai avuto una foto sincronizzata: assente, non un placeholder.
    assert body["homeLineup"]["bench"][0]["photoUrl"] is None
    assert [p["name"] for p in body["homeLineup"]["bench"]] == ["Paolo Verdi"]
    # Formazione ospite non pubblicata: assente, non vuota.
    assert body["awayLineup"] is None

    events = body["events"]
    assert [e["minuteElapsed"] for e in events] == [12, 63, 77]
    assert events[0]["minuteLabel"] == "12'"
    assert events[0]["relatedAthleteName"] == "Luca Bianchi"
    assert events[0]["athleteId"] == str(scorer.id)
    assert events[0]["relatedAthleteId"] == str(assister.id)
    assert events[0]["clubId"] == str(home.id)
    # L'evento ritrattato non deve comparire.
    assert all(e["minuteElapsed"] != 30 for e in events)
    # La copia normalizzata dello stesso gol (77') non deve duplicare la riga grezza.
    assert len([e for e in events if e["minuteElapsed"] == 77]) == 1


def test_live_fixture_without_recent_updates_is_reported_as_stale(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token = _register_and_login(client, "live-stale@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Feed Fermo")
    fantasy_round, fixture, _, _ = _build_live_fixture(
        db_session,
        league_id=league_id,
        competition_id=UUID(competition_ids[0]),
        provider_seed=971000,
    )
    db_session.commit()
    # Simula un feed fermo: la partita è live ma il dato non si aggiorna. Azzera
    # anche venue/arbitro per verificare che restino assenti, non un placeholder.
    db_session.query(Fixture).filter(Fixture.id == fixture.id).update(
        {
            Fixture.updated_at: datetime.now(UTC) - timedelta(minutes=30),
            Fixture.venue_name: None,
            Fixture.venue_city: None,
            Fixture.referee: None,
        }
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/partite/{fixture.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["feedState"] == "stale"
    assert body["feedStateLabel"] == "Dati fermi"
    # Nessun evento inventato per compensare il buco.
    assert body["events"] == []
    # Provider senza venue/arbitro per questa partita: assenti, non placeholder.
    assert body["venueName"] is None
    assert body["referee"] is None


def test_fixture_outside_the_turn_is_not_readable(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    """Senza il vincolo turno↔partita un id qualsiasi leggerebbe fixture altrui."""
    token = _register_and_login(client, "live-scope@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Scope")
    fantasy_round, _, _, _ = _build_live_fixture(
        db_session,
        league_id=league_id,
        competition_id=UUID(competition_ids[0]),
        provider_seed=972000,
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/partite/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "fixture_not_found"


def test_turn_list_exposes_feed_freshness(
    client: TestClient, db_session: Session, competition_ids: list[str]
) -> None:
    token = _register_and_login(client, "live-list@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Lista Live")
    fantasy_round, _, _, _ = _build_live_fixture(
        db_session,
        league_id=league_id,
        competition_id=UUID(competition_ids[0]),
        provider_seed=973000,
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    fixture_body = response.json()["fixtures"][0]
    assert fixture_body["updatedAt"] is not None
    assert fixture_body["feedState"] == "fresh"
    assert fixture_body["feedStateLabel"] == "Aggiornato"
    assert fixture_body["homeClubLogoUrl"] == "https://media.api-sports.io/football/teams/home.png"
