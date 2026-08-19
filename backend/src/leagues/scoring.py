"""Punteggio squadra e gol fantasy (EP07-05 / FR-SCO-03).

Motore puro: converte il totale dei fantavoti degli undici effettivi in gol
fantasy e confronta due squadre per produrre l'esito dello scontro diretto.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor

FIRST_GOAL_THRESHOLD = 66.0
POINTS_PER_ADDITIONAL_GOAL = 6.0

HOME_WIN = "home"
AWAY_WIN = "away"
DRAW = "draw"


def fantasy_goals_for_points(total_points: float) -> int:
    """FR-SCO-03: fino a 65,5 punti 0 gol; da 66 punti 1 gol, +1 ogni 6 punti."""
    if total_points < FIRST_GOAL_THRESHOLD:
        return 0
    return 1 + floor((total_points - FIRST_GOAL_THRESHOLD) / POINTS_PER_ADDITIONAL_GOAL)


@dataclass(frozen=True)
class MatchOutcome:
    home_fantasy_goals: int
    away_fantasy_goals: int
    outcome: str

    @classmethod
    def from_points(cls, *, home_points: float, away_points: float) -> MatchOutcome:
        home_goals = fantasy_goals_for_points(home_points)
        away_goals = fantasy_goals_for_points(away_points)
        return cls(
            home_fantasy_goals=home_goals,
            away_fantasy_goals=away_goals,
            outcome=compare_fantasy_goals(home_goals, away_goals),
        )


def compare_fantasy_goals(home_fantasy_goals: int, away_fantasy_goals: int) -> str:
    """Confronta i gol fantasy delle due squadre (decisione Beta, FR-SCO-03 §Eccezioni).

    L'eventuale scarto minimo tra squadre nella stessa fascia gol (stesso
    numero di gol fantasy pur con punteggio grezzo diverso) e' una decisione
    aperta nei requisiti: il default Beta dichiara pareggio, senza usare il
    punteggio grezzo come spareggio implicito.
    """
    if home_fantasy_goals > away_fantasy_goals:
        return HOME_WIN
    if home_fantasy_goals < away_fantasy_goals:
        return AWAY_WIN
    return DRAW
