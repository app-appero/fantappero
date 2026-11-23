"""Storico della stagione in corso dai nostri dati (1.3): somma per calciatore + club.

Presenze, minuti, gol, assist, gol subiti, parate, rigori parati, cartellini, porte inviolate
(regola del bonus: portiere con voto e squadra a zero) e media dei nostri voti. Solo partite
finite; il voto di una partita conta una volta anche se calcolato in più leghe.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from database.enums import FantasyRole, LeagueState
from fantasy_ratings.config import DEFAULT_FORMULA_VERSION
from fantasy_ratings.models import PlayerMatchRating
from leagues.models.competition import Competition
from leagues.models.league import League
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture, PlayerMatchStat
from sports_data.roster.models import Athlete
from sports_data.season_stats.current_season import (
    aggregate_current_season,
    materialize_current_season,
)
from sports_data.season_stats.models import AthleteSeasonStat

GK = 918_001
FW = 918_002
SEASON = 2026


def _stat_json(
    *,
    goals: int | None = None,
    assists: int | None = None,
    conceded: int | None = 0,
    saves: int | None = None,
    pen_saved: int | None = 0,
    yellow: int = 0,
    red: int = 0,
) -> dict[str, Any]:
    return {
        "games": {"minutes": 90, "position": "G", "rating": "6.5"},
        "goals": {"total": goals, "assists": assists, "conceded": conceded, "saves": saves},
        "penalty": {"saved": pen_saved, "missed": 0, "scored": 0},
        "cards": {"yellow": yellow, "red": red},
    }


@pytest.fixture
def setup(session: Session) -> dict[str, Any]:
    session.execute(delete(AthleteSeasonStat))
    serie_a = session.scalar(select(Competition).where(Competition.provider_id == 135))
    assert serie_a is not None
    season = session.scalar(
        select(SportSeason).where(
            SportSeason.competition_id == serie_a.id, SportSeason.year == SEASON
        )
    )
    if season is None:
        season = SportSeason(competition_id=serie_a.id, year=SEASON, is_current=True)
        session.add(season)
        session.flush()
    home = Club(provider_id=918_101, name="Casa FC")
    away = Club(provider_id=918_102, name="Ospiti FC")
    session.add_all([home, away])
    session.flush()
    gk = Athlete(provider_id=GK, canonical_name="Portiere Casa")
    fw = Athlete(provider_id=FW, canonical_name="Punta Casa")
    session.add_all([gk, fw])
    session.flush()

    def fixture(provider_id: int, status: str, home_goals: int, away_goals: int) -> Fixture:
        row = Fixture(
            provider_id=provider_id,
            sport_season_id=season.id,
            home_club_id=home.id,
            away_club_id=away.id,
            status_short=status,
            home_goals=home_goals,
            away_goals=away_goals,
        )
        session.add(row)
        session.flush()
        return row

    f1 = fixture(918_201, "FT", 1, 0)  # porta inviolata per la squadra di casa
    f2 = fixture(918_202, "FT", 2, 3)
    f3 = fixture(918_203, "AET", 0, 0)
    f4 = fixture(918_204, "2H", 0, 0)  # in corso: non conta

    def stat(fx: Fixture, athlete: Athlete, minutes: int, *, substitute: bool, **stats: Any):
        session.add(
            PlayerMatchStat(
                fixture_id=fx.id,
                athlete_id=athlete.id,
                athlete_provider_id=athlete.provider_id,
                club_id=home.id,
                minutes=minutes,
                is_substitute=substitute,
                stats_json=_stat_json(**stats),
                stats_hash=f"h{fx.provider_id}{athlete.provider_id}",
            )
        )

    def rating(
        fx: Fixture,
        athlete: Athlete,
        role: FantasyRole,
        display: float | None,
        fantasy: float | None,
        *,
        league_id: Any = None,
    ) -> None:
        session.add(
            PlayerMatchRating(
                fixture_id=fx.id,
                league_id=league_id,
                athlete_id=athlete.id,
                athlete_provider_id=athlete.provider_id,
                formula_version=DEFAULT_FORMULA_VERSION,
                role=role,
                minutes=90,
                eligible=display is not None,
                eligibility_reason="minutes_threshold" if display is not None else "no_minutes",
                base=6.0,
                raw_before_clamp=display or 6.0,
                raw=display or 6.0,
                display=display,
                stats_hash="x",
                fantasy_score=fantasy,
            )
        )

    league = League(name="Lega Storico", season_year=SEASON, state=LeagueState.ACTIVE)
    session.add(league)
    session.flush()

    # Portiere: due partite con voto (una a porta inviolata), una in corso che non conta.
    stat(f1, gk, 90, substitute=False, conceded=0, saves=4)
    rating(f1, gk, FantasyRole.P, 6.5, 7.5)
    stat(f2, gk, 90, substitute=False, conceded=3, saves=2, pen_saved=1)
    rating(f2, gk, FantasyRole.P, 5.5, 3.5)
    stat(f4, gk, 60, substitute=False, conceded=0, saves=1)
    rating(f4, gk, FantasyRole.P, 7.0, 8.0)

    # Attaccante: voto in f1 calcolato in due leghe (globale + lega), conta una volta; in f2
    # entra senza voto; in f3 resta in panchina (non è una presenza).
    stat(f1, fw, 80, substitute=False, goals=1, yellow=1, conceded=None)
    rating(f1, fw, FantasyRole.A, 7.0, 9.5)
    rating(f1, fw, FantasyRole.A, 7.0, 9.5, league_id=league.id)
    stat(f2, fw, 20, substitute=True, assists=1, conceded=None)
    rating(f2, fw, FantasyRole.A, None, None)
    stat(f3, fw, 0, substitute=True, conceded=None)
    session.flush()
    return {"home": home, "competition": serie_a, "gk": gk, "fw": fw}


def _by_athlete(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {
        row["athlete_provider_id"]: row for row in rows if row["athlete_provider_id"] in (GK, FW)
    }


def test_goalkeeper_aggregate_with_clean_sheets(session: Session, setup: dict) -> None:
    rows = _by_athlete(aggregate_current_season(session, season_year=SEASON))
    gk = rows[GK]
    assert gk["source"] == "fantappero"
    assert gk["club_id"] == setup["home"].id and gk["club_name"] == "Casa FC"
    assert gk["competition_id"] == setup["competition"].id
    assert gk["appearances"] == 2 and gk["lineups"] == 2
    assert gk["minutes"] == 180
    assert gk["votes"] == 2
    assert gk["rating"] == pytest.approx(6.0)  # media dei nostri voti (6,5 e 5,5)
    assert gk["fantasy_average"] == pytest.approx(5.5)
    assert gk["goals_conceded"] == 3
    assert gk["saves"] == 6
    assert gk["penalties_saved"] == 1
    assert gk["clean_sheets"] == 1  # solo f1: in f4 (in corso) non conta


def test_outfield_player_aggregate(session: Session, setup: dict) -> None:
    fw = _by_athlete(aggregate_current_season(session, season_year=SEASON))[FW]
    assert fw["appearances"] == 2  # f1 con voto e f2 senza; la panchina di f3 no
    assert fw["lineups"] == 1
    assert fw["minutes"] == 100
    assert fw["votes"] == 1  # f1 una volta sola, anche se votata in due leghe
    assert fw["rating"] == pytest.approx(7.0)
    assert fw["fantasy_average"] == pytest.approx(9.5)
    assert (fw["goals"], fw["assists"], fw["yellow_cards"], fw["red_cards"]) == (1, 1, 1, 0)
    assert fw["clean_sheets"] is None  # porte inviolate solo per i portieri


def test_materialize_rewrites_the_season_rows(session: Session, setup: dict) -> None:
    first = materialize_current_season(session, season_year=SEASON)
    second = materialize_current_season(session, season_year=SEASON)
    assert first == second
    count = session.scalar(
        select(func.count())
        .select_from(AthleteSeasonStat)
        .where(
            AthleteSeasonStat.season_year == SEASON,
            AthleteSeasonStat.source == "fantappero",
            AthleteSeasonStat.athlete_provider_id.in_([GK, FW]),
        )
    )
    assert count == 2
    stored = session.scalar(
        select(AthleteSeasonStat).where(AthleteSeasonStat.athlete_provider_id == GK)
    )
    assert stored is not None and stored.clean_sheets == 1 and stored.votes == 2
