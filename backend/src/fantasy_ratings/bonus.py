"""Motore puro di bonus e malus: eventi ufficiali sommati al voto (EP07-03).

FR-SCO-02: "Applicare una sola volta gli eventi approvati e sommarli al voto
statistico." Ogni componente legge un unico campo aggregato gia' deduplicato
dal provider (``goals.total``, ``cards.yellow`` ecc.) o un conteggio di
match_event attivi con chiave univoca (autogol): nessun evento puo' quindi
contribuire due volte allo stesso fantavoto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fantasy_ratings.bonus_config import BonusMalusConfig
from fantasy_ratings.config import RoleCode


@dataclass(frozen=True)
class BonusComponent:
    id: str
    count: int
    unit_value: float
    contribution: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "count": self.count,
            "unit_value": self.unit_value,
            "contribution": self.contribution,
        }


@dataclass(frozen=True)
class BonusMalusInput:
    goals: int = 0
    assists: int = 0
    yellow_card: bool = False
    red_card: bool = False
    own_goals: int = 0
    penalty_missed: int = 0
    penalty_saved: int = 0
    role: RoleCode | None = None
    team_goals_conceded: int | None = None


@dataclass(frozen=True)
class BonusMalusResult:
    config_version: str
    eligible: bool
    components: tuple[BonusComponent, ...]

    @property
    def total(self) -> float:
        return round(sum(item.contribution for item in self.components), 10)

    def as_dict(self) -> dict[str, Any]:
        return [item.as_dict() for item in self.components]


def reconstruct_total_from_stored(components: list[dict[str, Any]]) -> float:
    """Ricostruisce il totale bonus/malus dai componenti JSON persistiti."""
    return round(sum(float(item["contribution"]) for item in components), 10)


def compute_bonus_malus(
    data: BonusMalusInput,
    config: BonusMalusConfig,
    *,
    eligible: bool,
) -> BonusMalusResult:
    """Calcola i componenti bonus/malus per un calciatore-partita.

    ``eligible`` deve rispecchiare l'eleggibilita' del voto statistico
    (EP07-02): un calciatore senza voto non riceve bonus/malus (FR-RIN-01:
    "Il voto d'ufficio non include bonus o malus").
    """
    if not eligible:
        return BonusMalusResult(config_version=config.version, eligible=False, components=())

    components: list[BonusComponent] = []

    def add(component_id: str, count: int, unit_value: float) -> None:
        if count <= 0 or unit_value == 0:
            return
        components.append(
            BonusComponent(
                id=component_id,
                count=count,
                unit_value=unit_value,
                contribution=round(count * unit_value, 10),
            )
        )

    add("goal", data.goals, config.goal)
    add("assist", data.assists, config.assist)
    add("own_goal", data.own_goals, config.own_goal)
    add("penalty_missed", data.penalty_missed, config.penalty_missed)

    # FR-SCO-02: decisione aperta su doppia ammonizione/espulsione (default
    # Beta ``RED_SUPERSEDES_YELLOW``, l'unica policy oggi supportata):
    # l'espulsione assorbe l'ammonizione dello stesso episodio, evitando di
    # sommare -0.5 e -1 per un solo evento disciplinare.
    if data.red_card:
        add("red_card", 1, config.red_card)
    elif data.yellow_card:
        add("yellow_card", 1, config.yellow_card)

    if data.role == "P":
        add("penalty_saved", data.penalty_saved, config.penalty_saved)
        if data.team_goals_conceded is not None:
            add(
                "goalkeeper_goal_conceded",
                data.team_goals_conceded,
                config.goalkeeper_goal_conceded,
            )
            if data.team_goals_conceded == 0:
                add("goalkeeper_clean_sheet", 1, config.goalkeeper_clean_sheet)

    return BonusMalusResult(
        config_version=config.version,
        eligible=True,
        components=tuple(components),
    )
