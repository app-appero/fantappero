"""Storico della stagione in corso dai dati di FantApperò (release 1.3).

Per ogni calciatore + club + competizione della stagione: presenze, minuti, gol, assist, gol
subiti, parate, rigori parati, cartellini, porte inviolate e **media voto = media dei nostri
voti** (``player_match_ratings.display``). Solo partite finite (FT/AET/PEN): una partita in
corso cambierebbe i numeri a ogni minuto.

Scelta (efficienza su ~2.500 calciatori): **una sola query** legge una riga per
calciatore-partita della stagione (statistiche + voto già deduplicato fra leghe), la somma in
Python e **riscrive** le righe ``source = 'fantappero'`` della stagione in
``athlete_season_stats``. Le pagine leggono la tabella materializzata, non i dati per partita.
Il ricalcolo gira dopo ogni giornata (job periodico «Medie e Valore di mercato», che salta se i
voti non sono cambiati) e alla fine dell'import dello storico.

Voto della partita: i voti sono calcolati per lega (cambia solo la soglia minuti per
l'eleggibilità; il voto è lo stesso). Per calciatore-partita si prende il voto più alto fra
le leghe (``max(display)``): ha voto se lo ha in almeno una lega.

Porte inviolate: stessa regola del bonus (``fantasy_ratings.bonus.is_goalkeeper_clean_sheet``):
portiere con voto e squadra a zero gol subiti nella partita
(``fantasy_ratings.mapping.goals_conceded_by_club``). Per gli altri ruoli restano vuote.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import String, case, cast, delete, func, insert, select
from sqlalchemy.orm import Session

from fantasy_ratings.bonus import is_goalkeeper_clean_sheet
from fantasy_ratings.config import DEFAULT_FORMULA_VERSION
from fantasy_ratings.mapping import goals_conceded_by_club
from fantasy_ratings.models import PlayerMatchRating
from fantasy_turns.readiness import FINISHED_FIXTURE_STATUSES
from leagues.models.competition import Competition
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture, PlayerMatchStat
from sports_data.season_stats.models import AthleteSeasonStat
from sports_data.season_stats.seasons import SOURCE_FANTAPPERO, UNKNOWN_PROVIDER_ID


@dataclass
class _Accumulator:
    athlete_provider_id: int
    athlete_id: UUID | None
    club_provider_id: int
    club_id: UUID | None
    club_name: str | None
    competition_provider_id: int
    competition_id: UUID | None
    competition_name: str | None
    is_goalkeeper: bool = False
    appearances: int = 0
    lineups: int = 0
    minutes: int = 0
    vote_sum: float = 0.0
    votes: int = 0
    fantasy_sum: float = 0.0
    fantasy_count: int = 0
    goals: int = 0
    assists: int = 0
    goals_conceded: int = 0
    saves: int = 0
    penalties_saved: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    clean_sheets: int = 0

    def as_row(self, season_year: int) -> dict[str, Any]:
        return {
            "athlete_provider_id": self.athlete_provider_id,
            "athlete_id": self.athlete_id,
            "season_year": season_year,
            "source": SOURCE_FANTAPPERO,
            "club_provider_id": self.club_provider_id,
            "club_id": self.club_id,
            "club_name": self.club_name,
            "competition_provider_id": self.competition_provider_id,
            "competition_id": self.competition_id,
            "competition_name": self.competition_name,
            "appearances": self.appearances,
            "lineups": self.lineups,
            "minutes": self.minutes,
            "rating": (self.vote_sum / self.votes) if self.votes else None,
            "votes": self.votes,
            "fantasy_average": (
                self.fantasy_sum / self.fantasy_count if self.fantasy_count else None
            ),
            "goals": self.goals,
            "assists": self.assists,
            "goals_conceded": self.goals_conceded,
            "saves": self.saves,
            "penalties_saved": self.penalties_saved,
            "yellow_cards": self.yellow_cards,
            "red_cards": self.red_cards,
            # Porte inviolate: solo portieri (decisione del 22/11).
            "clean_sheets": self.clean_sheets if self.is_goalkeeper else None,
            "snapshot_id": None,
        }


def _json_number(*path: str) -> Any:
    """Numero (come testo) da ``stats_json``; null o non numerico ⇒ NULL, mai errori di cast."""
    element = PlayerMatchStat.stats_json[path]
    return case(
        (func.jsonb_typeof(element) == "number", element.astext),
        else_=None,
    )


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _votes_subquery(season_year: int) -> Any:
    """Un voto per calciatore-partita: il più alto fra le leghe (stessa formula)."""
    return (
        select(
            PlayerMatchRating.fixture_id.label("fixture_id"),
            PlayerMatchRating.athlete_provider_id.label("athlete_provider_id"),
            func.max(PlayerMatchRating.display).label("vote"),
            func.max(PlayerMatchRating.fantasy_score).label("fantasy"),
            func.max(cast(PlayerMatchRating.role, String)).label("role"),
        )
        .join(Fixture, Fixture.id == PlayerMatchRating.fixture_id)
        .join(SportSeason, SportSeason.id == Fixture.sport_season_id)
        .where(
            SportSeason.year == season_year,
            PlayerMatchRating.formula_version == DEFAULT_FORMULA_VERSION,
            Fixture.status_short.in_(sorted(FINISHED_FIXTURE_STATUSES)),
        )
        .group_by(PlayerMatchRating.fixture_id, PlayerMatchRating.athlete_provider_id)
        .subquery("season_votes")
    )


def _season_match_rows(session: Session, season_year: int) -> Iterable[Any]:
    votes = _votes_subquery(season_year)
    stmt = (
        select(
            PlayerMatchStat.athlete_provider_id,
            PlayerMatchStat.athlete_id,
            PlayerMatchStat.club_id,
            PlayerMatchStat.minutes,
            PlayerMatchStat.is_substitute,
            Fixture.home_club_id,
            Fixture.away_club_id,
            Fixture.home_goals,
            Fixture.away_goals,
            Competition.id.label("competition_id"),
            Competition.provider_id.label("competition_provider_id"),
            Competition.name.label("competition_name"),
            Club.provider_id.label("club_provider_id"),
            Club.name.label("club_name"),
            _json_number("goals", "total").label("goals"),
            _json_number("goals", "assists").label("assists"),
            _json_number("goals", "conceded").label("goals_conceded"),
            _json_number("goals", "saves").label("saves"),
            _json_number("penalty", "saved").label("penalties_saved"),
            _json_number("cards", "yellow").label("yellow_cards"),
            _json_number("cards", "red").label("red_cards"),
            votes.c.vote,
            votes.c.fantasy,
            votes.c.role,
        )
        .join(Fixture, Fixture.id == PlayerMatchStat.fixture_id)
        .join(SportSeason, SportSeason.id == Fixture.sport_season_id)
        .join(Competition, Competition.id == SportSeason.competition_id)
        .outerjoin(Club, Club.id == PlayerMatchStat.club_id)
        .outerjoin(
            votes,
            (votes.c.fixture_id == PlayerMatchStat.fixture_id)
            & (votes.c.athlete_provider_id == PlayerMatchStat.athlete_provider_id),
        )
        .where(
            SportSeason.year == season_year,
            Fixture.status_short.in_(sorted(FINISHED_FIXTURE_STATUSES)),
        )
    )
    return session.execute(stmt).all()


def aggregate_current_season(session: Session, *, season_year: int) -> list[dict[str, Any]]:
    """Righe ``athlete_season_stats`` (come dict) della stagione dai nostri dati per partita."""
    accumulators: dict[tuple[int, int, int], _Accumulator] = {}
    for row in _season_match_rows(session, season_year):
        minutes = _to_int(row.minutes)
        vote = row.vote
        if minutes <= 0 and vote is None:
            continue  # in panchina senza entrare: non è una presenza
        club_provider_id = (
            int(row.club_provider_id) if row.club_provider_id is not None else UNKNOWN_PROVIDER_ID
        )
        key = (int(row.athlete_provider_id), club_provider_id, int(row.competition_provider_id))
        acc = accumulators.get(key)
        if acc is None:
            acc = _Accumulator(
                athlete_provider_id=int(row.athlete_provider_id),
                athlete_id=row.athlete_id,
                club_provider_id=club_provider_id,
                club_id=row.club_id,
                club_name=row.club_name,
                competition_provider_id=int(row.competition_provider_id),
                competition_id=row.competition_id,
                competition_name=row.competition_name,
            )
            accumulators[key] = acc
        if acc.athlete_id is None and row.athlete_id is not None:
            acc.athlete_id = row.athlete_id
        acc.appearances += 1
        if row.is_substitute is False:
            acc.lineups += 1
        acc.minutes += minutes
        acc.goals += _to_int(row.goals)
        acc.assists += _to_int(row.assists)
        acc.goals_conceded += _to_int(row.goals_conceded)
        acc.saves += _to_int(row.saves)
        acc.penalties_saved += _to_int(row.penalties_saved)
        acc.yellow_cards += _to_int(row.yellow_cards)
        acc.red_cards += _to_int(row.red_cards)
        if row.role == "P":
            acc.is_goalkeeper = True
        if vote is not None:
            acc.votes += 1
            acc.vote_sum += float(vote)
            if row.fantasy is not None:
                acc.fantasy_count += 1
                acc.fantasy_sum += float(row.fantasy)
            conceded = goals_conceded_by_club(
                club_id=row.club_id,
                home_club_id=row.home_club_id,
                away_club_id=row.away_club_id,
                home_goals=row.home_goals,
                away_goals=row.away_goals,
            )
            if is_goalkeeper_clean_sheet(row.role, conceded):
                acc.clean_sheets += 1
    return [acc.as_row(season_year) for acc in accumulators.values()]


def materialize_current_season(session: Session, *, season_year: int) -> int:
    """Riscrive le righe FantApperò della stagione. Idempotente. Ritorna le righe scritte."""
    rows = aggregate_current_season(session, season_year=season_year)
    session.execute(
        delete(AthleteSeasonStat).where(
            AthleteSeasonStat.season_year == season_year,
            AthleteSeasonStat.source == SOURCE_FANTAPPERO,
        )
    )
    if rows:
        session.execute(insert(AthleteSeasonStat), rows)
    session.flush()
    return len(rows)


__all__ = ["aggregate_current_season", "materialize_current_season"]
