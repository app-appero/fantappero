"""Classifica e criteri di parità (EP07-06 / FR-CLS-01).

Motore puro: aggrega i risultati H2H finali in un tabellino per squadra e
ordina la classifica. Sempre ricalcolata dall'origine (i risultati persistiti
in ``league_calendar_slots``), mai accumulata in modo incrementale: un
ricalcolo sovrascrive il contributo di ogni incontro invece di sommarlo due
volte (FR-CLS-01 "Regole e controlli").
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

# Punteggio vittoria/pareggio/sconfitta: decisione aperta in FR-CLS-01
# ("da approvare prima dell'implementazione"). Default Beta: 3-1-0, lo
# standard calcistico.
STANDARD_POINTS_WIN = 3
STANDARD_POINTS_DRAW = 1
STANDARD_POINTS_LOSS = 0

HOME_WIN = "home"
AWAY_WIN = "away"
DRAW = "draw"


@dataclass(frozen=True)
class MatchResult:
    home_team_id: UUID
    away_team_id: UUID
    home_fantasy_goals: int
    away_fantasy_goals: int
    outcome: str


@dataclass(frozen=True)
class TeamRecord:
    fantasy_team_id: UUID
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    fantasy_goals_for: int = 0
    fantasy_goals_against: int = 0

    @property
    def points(self) -> int:
        return (
            self.won * STANDARD_POINTS_WIN
            + self.drawn * STANDARD_POINTS_DRAW
            + self.lost * STANDARD_POINTS_LOSS
        )

    @property
    def goal_difference(self) -> int:
        return self.fantasy_goals_for - self.fantasy_goals_against

    def as_dict(self) -> dict[str, Any]:
        return {
            "fantasyTeamId": str(self.fantasy_team_id),
            "played": self.played,
            "won": self.won,
            "drawn": self.drawn,
            "lost": self.lost,
            "fantasyGoalsFor": self.fantasy_goals_for,
            "fantasyGoalsAgainst": self.fantasy_goals_against,
            "points": self.points,
        }


def _add_match(
    record: TeamRecord, *, goals_for: int, goals_against: int, result: str
) -> TeamRecord:
    won = record.won + (1 if result == "won" else 0)
    drawn = record.drawn + (1 if result == "drawn" else 0)
    lost = record.lost + (1 if result == "lost" else 0)
    return replace(
        record,
        played=record.played + 1,
        won=won,
        drawn=drawn,
        lost=lost,
        fantasy_goals_for=record.fantasy_goals_for + goals_for,
        fantasy_goals_against=record.fantasy_goals_against + goals_against,
    )


def build_standings(
    team_ids: list[UUID],
    matches: list[MatchResult],
) -> dict[UUID, TeamRecord]:
    """Aggrega da zero i risultati finali: nessun accumulo incrementale."""
    records = {team_id: TeamRecord(fantasy_team_id=team_id) for team_id in team_ids}
    for match in matches:
        if match.home_team_id not in records or match.away_team_id not in records:
            continue
        if match.outcome == HOME_WIN:
            home_result, away_result = "won", "lost"
        elif match.outcome == AWAY_WIN:
            home_result, away_result = "lost", "won"
        else:
            home_result, away_result = "drawn", "drawn"

        records[match.home_team_id] = _add_match(
            records[match.home_team_id],
            goals_for=match.home_fantasy_goals,
            goals_against=match.away_fantasy_goals,
            result=home_result,
        )
        records[match.away_team_id] = _add_match(
            records[match.away_team_id],
            goals_for=match.away_fantasy_goals,
            goals_against=match.home_fantasy_goals,
            result=away_result,
        )
    return records


def rank_standings(
    records: dict[UUID, TeamRecord],
    *,
    team_names: dict[UUID, str] | None = None,
) -> list[TeamRecord]:
    """Ordina per criteri di parità (decisione Beta, FR-CLS-01 §Eccezioni).

    Punti desc, differenza reti fantasy desc, gol fantasy fatti desc, nome
    squadra asc come spareggio finale stabile e deterministico. Criteri
    completi di parità restano una decisione aperta nei requisiti.
    """
    names = team_names or {}

    def sort_key(record: TeamRecord) -> tuple[int, int, int, str]:
        return (
            -record.points,
            -record.goal_difference,
            -record.fantasy_goals_for,
            names.get(record.fantasy_team_id, str(record.fantasy_team_id)),
        )

    return sorted(records.values(), key=sort_key)
