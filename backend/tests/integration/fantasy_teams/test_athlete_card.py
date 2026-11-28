"""Scheda calciatore: dati provider già salvati e rosa della lega corrente."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import FantasyRole, LeagueMemberRole
from database.session import create_session_factory
from fantasy_ratings.config import DEFAULT_FORMULA_VERSION
from fantasy_ratings.models import PlayerMatchRating
from leagues.models.competition import Competition
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture, PlayerMatchStat
from sports_data.listone.generate import pick_active_memberships
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete, SquadMembership, Transfer
from sports_data.season_stats.current_season import aggregate_current_season


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


def test_athlete_card_club_matches_the_listone_with_several_active_memberships(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA notte 24-25/11: Aitor Fernández «Villarreal» nella scheda e «Osasuna» nel listone.
    Con più membership attive la scheda sceglie come il listone: vince il club d'arrivo
    dell'ultimo trasferimento, anche se l'altra membership è della rosa del fornitore e più
    recente."""
    token, _user_id = _register_and_login(client, "card.club@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Lega Scheda Club", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201
    league_id = created.json()["id"]

    villarreal = Club(provider_id=880451, name="Villarreal")
    osasuna = Club(provider_id=880452, name="Osasuna")
    db_session.add_all([villarreal, osasuna])
    db_session.flush()
    competition_id = UUID(competition_ids[0])
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id, SportSeason.year == 2026
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()

    athlete = Athlete(provider_id=880453, canonical_name="Aitor Fernández")
    db_session.add(athlete)
    db_session.flush()
    now = datetime.now(UTC)
    # Prima la membership sbagliata: è quella che la scheda prendeva (la prima attiva).
    db_session.add(
        SquadMembership(
            athlete_id=athlete.id,
            club_id=villarreal.id,
            sport_season_id=season.id,
            shirt_number=13,
            provider_position_raw="Goalkeeper",
            is_active=True,
            source="squads",
            updated_at=now,
        )
    )
    db_session.flush()
    db_session.add(
        SquadMembership(
            athlete_id=athlete.id,
            club_id=osasuna.id,
            sport_season_id=season.id,
            shirt_number=1,
            provider_position_raw="Goalkeeper",
            is_active=True,
            source="players",
            updated_at=now - timedelta(days=1),
        )
    )
    db_session.add(
        Transfer(
            athlete_id=athlete.id,
            transfer_date=date(2025, 7, 1),
            from_club_id=villarreal.id,
            to_club_id=osasuna.id,
            transfer_type="Loan",
            provider_key="athlete-card-aitor-2025",
        )
    )
    db_session.commit()

    assert pick_active_memberships(db_session, 2026)[athlete.id].club_id == osasuna.id
    card = client.get(
        f"/leagues/{league_id}/calciatori/{athlete.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert card.status_code == 200
    assert card.json()["clubName"] == "Osasuna"
    assert card.json()["shirtNumber"] == 1


def test_athlete_card_season_average_rating_uses_fantappero_votes(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """QA 28/11 (3.15): la «Media voto» in alto nella scheda era la media dei voti del
    FORNITORE (Mbappé 8,0 contro 7,82 del listone e della riga 2026/27 della carriera).
    Quella documentata è la media dei NOSTRI voti (`player_match_ratings.display`, formula in
    uso): la scheda prende il voto di ogni partita da lì, il più alto fra lega e globale.
    La «Media fantacalcio» resta quella dei fantavoti."""
    token, _user_id = _register_and_login(client, "card.average@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Lega Scheda Media", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201
    league_id = UUID(created.json()["id"])

    home = Club(provider_id=880461, name="Casa Media")
    away = Club(provider_id=880462, name="Ospite Media")
    db_session.add_all([home, away])
    db_session.flush()
    competition_id = UUID(competition_ids[0])
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id, SportSeason.year == 2026
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()
    athlete = Athlete(provider_id=880463, canonical_name="Media Voto")
    db_session.add(athlete)
    db_session.flush()
    db_session.add(
        SquadMembership(
            athlete_id=athlete.id,
            club_id=home.id,
            sport_season_id=season.id,
            shirt_number=9,
            provider_position_raw="Attacker",
            is_active=True,
            source="squads",
        )
    )
    db_session.add(
        RoleAssignment(
            athlete_id=athlete.id,
            season_year=2026,
            role=FantasyRole.A,
            mapping_version="v1.0.0",
            provider_position_raw="Attacker",
        )
    )

    def rating(
        fixture: Fixture,
        number: int,
        display: float | None,
        fantasy_score: float | None,
        *,
        league: UUID | None = None,
        formula: str = DEFAULT_FORMULA_VERSION,
    ) -> None:
        db_session.add(
            PlayerMatchRating(
                fixture_id=fixture.id,
                league_id=league,
                athlete_id=athlete.id,
                athlete_provider_id=athlete.provider_id,
                formula_version=formula,
                role=FantasyRole.A,
                minutes=90,
                eligible=display is not None,
                eligibility_reason="minutes_threshold" if display is not None else "no_minutes",
                base=6.0,
                raw_before_clamp=display or 6.0,
                raw=display or 6.0,
                display=display,
                stats_hash=f"avg{number}",
                fantasy_score=fantasy_score,
            )
        )

    def match(number: int, provider_rating: str, *, status: str = "FT") -> Fixture:
        fixture = Fixture(
            provider_id=8804700 + number,
            sport_season_id=season.id,
            home_club_id=home.id,
            away_club_id=away.id,
            kickoff_at=datetime.now(UTC) - timedelta(days=number),
            status_short=status,
            home_goals=1,
            away_goals=0,
        )
        db_session.add(fixture)
        db_session.flush()
        db_session.add(
            PlayerMatchStat(
                fixture_id=fixture.id,
                athlete_id=athlete.id,
                athlete_provider_id=athlete.provider_id,
                club_id=home.id,
                minutes=90,
                is_substitute=False,
                provider_rating=provider_rating,
                stats_json={"goals": {"total": 1, "assists": 0}},
                stats_hash=f"avg{number}",
            )
        )
        return fixture

    # Partita 1: voto del fornitore 9,0, nostro 7,0 (fantavoto 9,0).
    rating(match(1, "9.0"), 1, 7.0, 9.0)
    # Partita 2: fornitore 8,0, nostro 6,0 (fantavoto 7,0). La riga di un'altra formula
    # (10,0) non conta.
    second = match(2, "8.0")
    rating(second, 2, 6.0, 7.0)
    rating(second, 2, 10.0, None, formula="vecchia-formula")
    # Partita 3: nostro voto globale 7,5 e di lega 8,0, senza fantavoto: vince il più alto
    # (8,0) ed entra nella media voto, non nella fantamedia.
    third = match(3, "6.5")
    rating(third, 3, 7.5, None)
    rating(third, 3, 8.0, None, league=league_id)
    # Partita 4: in corso, non conta nella media (il «voto live» resta quello del fornitore,
    # perché non c'è ancora un fantavoto).
    rating(match(4, "9.9", status="2H"), 4, 9.5, None)
    # Partita 5: il fornitore dà 7,0, noi nessun voto: non entra nella media voto.
    match(5, "7.0")
    db_session.commit()

    card = client.get(
        f"/leagues/{league_id}/calciatori/{athlete.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert card.status_code == 200
    body = card.json()
    stats = body["seasonStats"]
    assert stats["matches"] == 4
    assert stats["goals"] == 4
    # Nostri voti: (7,0 + 6,0 + 8,0) / 3 = 7,0. Fornitore: (9,0 + 8,0 + 6,5 + 7,0) / 4 = 7,63.
    assert stats["averageRating"] == pytest.approx(7.0)
    # Fantavoti: (9,0 + 7,0) / 2 = 8,0, come prima.
    assert stats["fantasyAverage"] == pytest.approx(8.0)
    assert body["live"] == {"score": pytest.approx(9.9), "isFantasy": False}

    # Stessa media della riga 2026/27 della carriera e del listone (`athlete_season_stats`).
    season_rows = [
        row
        for row in aggregate_current_season(db_session, season_year=2026)
        if row["athlete_provider_id"] == athlete.provider_id
    ]
    assert len(season_rows) == 1
    assert stats["averageRating"] == pytest.approx(season_rows[0]["rating"])
