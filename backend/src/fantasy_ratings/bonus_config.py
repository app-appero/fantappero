"""Configurazione versionata di bonus e malus (EP07-03 / FR-SCO-02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_BONUS_VERSION = "bonus-beta-v0.1"
DEFAULT_BONUS_CARD = "EP07-03"

# Valori da FR-SCO-02 (Requisiti Funzionali MVP v0.1).
# "Doppia ammonizione ed espulsione" e' una decisione aperta nel documento
# (vedi tabella §Decisioni da chiudere): questo default Beta applica soltanto
# il malus espulsione quando espulsione e ammonizione coincidono nello stesso
# evento, per non contare due volte la stessa infrazione disciplinare.
RED_SUPERSEDES_YELLOW = "red_supersedes_yellow"

BETA_V0_1: dict[str, Any] = {
    "version": DEFAULT_BONUS_VERSION,
    "card": DEFAULT_BONUS_CARD,
    "goal": 3.0,
    "assist": 1.0,
    "yellow_card": -0.5,
    "red_card": -1.0,
    "own_goal": -2.0,
    "penalty_missed": -3.0,
    "penalty_saved": 3.0,
    "goalkeeper_goal_conceded": -1.0,
    "goalkeeper_clean_sheet": 1.0,
    "double_card_policy": RED_SUPERSEDES_YELLOW,
}


@dataclass(frozen=True)
class BonusMalusConfig:
    version: str
    card: str
    goal: float
    assist: float
    yellow_card: float
    red_card: float
    own_goal: float
    penalty_missed: float
    penalty_saved: float
    goalkeeper_goal_conceded: float
    goalkeeper_clean_sheet: float
    double_card_policy: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "card": self.card,
            "goal": self.goal,
            "assist": self.assist,
            "yellow_card": self.yellow_card,
            "red_card": self.red_card,
            "own_goal": self.own_goal,
            "penalty_missed": self.penalty_missed,
            "penalty_saved": self.penalty_saved,
            "goalkeeper_goal_conceded": self.goalkeeper_goal_conceded,
            "goalkeeper_clean_sheet": self.goalkeeper_clean_sheet,
            "double_card_policy": self.double_card_policy,
        }


def default_bonus_config() -> BonusMalusConfig:
    return load_bonus_config(BETA_V0_1)


def load_bonus_config(raw: dict[str, Any] | None = None) -> BonusMalusConfig:
    payload = raw if raw is not None else BETA_V0_1
    required = (
        "version",
        "goal",
        "assist",
        "yellow_card",
        "red_card",
        "own_goal",
        "penalty_missed",
        "penalty_saved",
        "goalkeeper_goal_conceded",
        "goalkeeper_clean_sheet",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"config bonus_malus missing keys: {missing}")
    return BonusMalusConfig(
        version=str(payload["version"]),
        card=str(payload.get("card", DEFAULT_BONUS_CARD)),
        goal=float(payload["goal"]),
        assist=float(payload["assist"]),
        yellow_card=float(payload["yellow_card"]),
        red_card=float(payload["red_card"]),
        own_goal=float(payload["own_goal"]),
        penalty_missed=float(payload["penalty_missed"]),
        penalty_saved=float(payload["penalty_saved"]),
        goalkeeper_goal_conceded=float(payload["goalkeeper_goal_conceded"]),
        goalkeeper_clean_sheet=float(payload["goalkeeper_clean_sheet"]),
        double_card_policy=str(payload.get("double_card_policy", RED_SUPERSEDES_YELLOW)),
    )
