"""Valore di mercato («Valore») e media stagionale: costanti e formule pure (release 1.3).

Tutte le costanti della formula stanno qui, documentate; nessuna lettura dal database.
Il calcolo su tutto il listone e la scrittura della tabella sono in
``market.valuation_service``; la spiegazione per l'operatore, con la tabella degli esempi, in
``docs/operations/valore_di_mercato_e_storico.md``.

Formula (approvata sul canvas «Proposte 1.3», scheda Valore di mercato):

1. Per ogni stagione s (due fa, la scorsa, quella in corso) e per ogni ruolo r del listone:
   la media voto di ogni calciatore si «restringe» verso la media del ruolo in base alle
   presenze con voto n::

       media_ristretta = (n · media + K · media_ruolo) / (n + K)        K = SHRINK_APPEARANCES

   così 3 belle partite non fanno un titolare. Poi si prende il **percentile nel ruolo**
   (0..1, a rango medio) della media ristretta: confrontare posizioni e non voti rende
   omogenee le medie del fornitore (stagioni passate) e i nostri voti (stagione in corso).
2. Una stagione senza dati vale ``MISSING_SEASON_INDEX`` (sotto la mediana: chi non ha
   giocato non è un titolare sicuro).
3. I percentili si combinano con i pesi del canvas: stagione in corso fino al 50%, che
   cresce con le presenze con voto (pieno a ``CURRENT_FULL_WEIGHT_APPEARANCES``); il peso
   che le manca va alle due stagioni passate in proporzione 30:20.
4. L'indice combinato p passa per una curva convessa per ruolo, in crediti del budget di
   riferimento (1000, il default delle leghe)::

       valore_rif = FLOOR + (TOP_ruolo − FLOOR) · p ** CURVE_EXPONENT

5. I crediti della lega sono proporzionali al suo budget, arrotondati, almeno 1.

Chi non ha storico (nessuna stagione con dati) ha p = MISSING_SEASON_INDEX, cioè il
**valore base del ruolo** (``base_reference_value``).
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sports_data.season_stats.seasons import season_label

# -- budget -------------------------------------------------------------------

#: Budget a cui si riferiscono i valori calcolati: il default delle leghe
#: (``leagues.validators.STANDARD_TOTAL_CREDITS`` e ``league_rules.total_credits``).
REFERENCE_BUDGET = 1000
#: Un partecipante non offre meno di 1 credito: il Valore non scende sotto.
MIN_LEAGUE_CREDITS = 1

# -- pesi delle stagioni (canvas) ---------------------------------------------

WEIGHT_CURRENT_MAX = 0.50
WEIGHT_PREVIOUS = 0.30
WEIGHT_TWO_SEASONS_AGO = 0.20
#: Presenze con voto oltre le quali la stagione in corso pesa il 50% pieno.
CURRENT_FULL_WEIGHT_APPEARANCES = 15

# -- poche presenze: riduzione verso la media del ruolo -----------------------

#: Presenze «virtuali» alla media del ruolo aggiunte a ogni calciatore.
SHRINK_APPEARANCES = 8

# -- stagione senza dati / nessuno storico ------------------------------------

#: Percentile di una stagione senza dati (anche: chi non ha storico ⇒ valore base del ruolo).
MISSING_SEASON_INDEX = 0.33

# -- curva in crediti ---------------------------------------------------------

#: Convessità: i campioni costano molto più della media.
CURVE_EXPONENT = 2.4
#: Crediti (budget di riferimento) del peggiore del ruolo.
FLOOR_REFERENCE_CREDITS = 1.0
#: Crediti (budget di riferimento) del migliore del ruolo (percentile 1).
TOP_REFERENCE_CREDITS: dict[str, float] = {"P": 30.0, "D": 32.0, "C": 48.0, "A": 66.0}

#: Decimali della media stagionale mostrata.
SEASON_AVERAGE_DECIMALS = 2

ROLES = ("P", "D", "C", "A")


# -- tipi ---------------------------------------------------------------------


@dataclass(frozen=True)
class SeasonSample:
    """Media voto e partite che la compongono (righe della stagione già sommate)."""

    rating: float | None
    appearances: int

    @property
    def usable(self) -> bool:
        return self.rating is not None and self.appearances > 0


@dataclass(frozen=True)
class SeasonWeights:
    current: float
    previous: float
    two_seasons_ago: float

    def as_dict(self) -> dict[str, float]:
        return {
            "current": round(self.current, 4),
            "previous": round(self.previous, 4),
            "twoSeasonsAgo": round(self.two_seasons_ago, 4),
        }


@dataclass(frozen=True)
class ValuationInput:
    """Un calciatore del listone: ruolo ufficiale e media di ogni stagione."""

    key: Hashable
    role: str
    current: SeasonSample | None = None
    previous: SeasonSample | None = None
    two_seasons_ago: SeasonSample | None = None


@dataclass(frozen=True)
class Valuation:
    key: Hashable
    role: str
    value_index: float
    reference_value: float
    weights: SeasonWeights
    percentiles: dict[str, float | None] = field(default_factory=dict)
    has_history: bool = False

    def components(self) -> dict[str, Any]:
        return {
            "weights": self.weights.as_dict(),
            "percentiles": {
                slot: (round(value, 4) if value is not None else None)
                for slot, value in self.percentiles.items()
            },
            "hasHistory": self.has_history,
        }


@dataclass(frozen=True)
class SeasonAverage:
    """Media stagionale mostrata nelle liste del mercato."""

    value: float
    season_year: int
    is_current: bool

    @property
    def season_label(self) -> str:
        return season_label(self.season_year)


# -- funzioni pure ------------------------------------------------------------


def combine_rows(rows: Iterable[tuple[float | None, int | None]]) -> SeasonSample:
    """Media pesata per presenze delle righe di una stagione (es. trasferimento a metà).

    Ogni riga è ``(media, presenze)``. Una riga con media ma presenze mancanti conta 1.
    """
    weighted = 0.0
    total = 0
    for rating, appearances in rows:
        if rating is None:
            continue
        weight = appearances if appearances is not None and appearances > 0 else 1
        weighted += float(rating) * weight
        total += weight
    if total == 0:
        return SeasonSample(rating=None, appearances=0)
    return SeasonSample(rating=weighted / total, appearances=total)


def season_weights(current_appearances: int) -> SeasonWeights:
    """Pesi del canvas; il peso che manca alla stagione in corso va alle passate (30:20)."""
    progress = min(1.0, max(0, current_appearances) / CURRENT_FULL_WEIGHT_APPEARANCES)
    current = WEIGHT_CURRENT_MAX * progress
    spare = WEIGHT_CURRENT_MAX - current
    past_total = WEIGHT_PREVIOUS + WEIGHT_TWO_SEASONS_AGO
    return SeasonWeights(
        current=current,
        previous=WEIGHT_PREVIOUS + spare * WEIGHT_PREVIOUS / past_total,
        two_seasons_ago=WEIGHT_TWO_SEASONS_AGO + spare * WEIGHT_TWO_SEASONS_AGO / past_total,
    )


def shrink_rating(
    rating: float,
    appearances: int,
    role_mean: float,
    *,
    strength: int = SHRINK_APPEARANCES,
) -> float:
    """Media ristretta verso quella del ruolo: con poche presenze conta di più la media."""
    n = max(0, appearances)
    return (n * rating + strength * role_mean) / (n + strength)


def mid_rank_percentiles(values: Mapping[Hashable, float]) -> dict[Hashable, float]:
    """Percentile a rango medio in (0, 1): (sotto + metà degli uguali) / totale.

    Con un solo valore il percentile è 0.5; i pari merito hanno lo stesso percentile.
    """
    ordered = sorted(values.values())
    count = len(ordered)
    if count == 0:
        return {}
    result: dict[Hashable, float] = {}
    for key, value in values.items():
        below = bisect_left(ordered, value)
        equal = bisect_right(ordered, value) - below
        result[key] = (below + 0.5 * equal) / count
    return result


def value_curve(index: float, role: str) -> float:
    """Crediti (budget di riferimento) per l'indice combinato ``index`` nel ruolo ``role``."""
    top = TOP_REFERENCE_CREDITS[role]
    bounded = min(1.0, max(0.0, index))
    return FLOOR_REFERENCE_CREDITS + (top - FLOOR_REFERENCE_CREDITS) * bounded**CURVE_EXPONENT


def base_reference_value(role: str) -> float:
    """Valore base del ruolo: quello di chi non ha storico."""
    return value_curve(MISSING_SEASON_INDEX, role)


def credits_for_budget(reference_value: float, budget: int) -> int:
    """Crediti per una lega con budget ``budget``: proporzionali, arrotondati, almeno 1."""
    scaled = reference_value * max(0, budget) / REFERENCE_BUDGET
    return max(MIN_LEAGUE_CREDITS, int(math.floor(scaled + 0.5)))


def select_season_average(
    *,
    current_season_year: int,
    current: SeasonSample | None,
    previous: SeasonSample | None,
) -> SeasonAverage | None:
    """Media mostrata nelle liste del mercato.

    - stagione in corso se il calciatore ha almeno un voto (``is_current``: verde);
    - altrimenti la stagione scorsa (per la 2026/27: la media del fornitore della 2025/26,
      etichetta «25/26», rossa);
    - altrimenti nessuna.
    """
    if current is not None and current.usable:
        assert current.rating is not None
        return SeasonAverage(
            value=round(current.rating, SEASON_AVERAGE_DECIMALS),
            season_year=current_season_year,
            is_current=True,
        )
    if previous is not None and previous.usable:
        assert previous.rating is not None
        return SeasonAverage(
            value=round(previous.rating, SEASON_AVERAGE_DECIMALS),
            season_year=current_season_year - 1,
            is_current=False,
        )
    return None


_SLOTS = ("current", "previous", "twoSeasonsAgo")


def _slot_sample(item: ValuationInput, slot: str) -> SeasonSample | None:
    if slot == "current":
        return item.current
    if slot == "previous":
        return item.previous
    return item.two_seasons_ago


def _role_mean(samples: Sequence[SeasonSample]) -> float:
    total = sum(sample.appearances for sample in samples)
    return sum(float(sample.rating or 0.0) * sample.appearances for sample in samples) / total


def season_percentiles(inputs: Sequence[ValuationInput], slot: str) -> dict[Hashable, float]:
    """Percentile nel ruolo della media ristretta, per una stagione (``slot``)."""
    by_role: dict[str, list[tuple[Hashable, SeasonSample]]] = defaultdict(list)
    for item in inputs:
        sample = _slot_sample(item, slot)
        if sample is not None and sample.usable:
            by_role[item.role].append((item.key, sample))
    result: dict[Hashable, float] = {}
    for population in by_role.values():
        mean = _role_mean([sample for _, sample in population])
        shrunk = {
            key: shrink_rating(float(sample.rating or 0.0), sample.appearances, mean)
            for key, sample in population
        }
        result.update(mid_rank_percentiles(shrunk))
    return result


def compute_valuations(inputs: Sequence[ValuationInput]) -> dict[Hashable, Valuation]:
    """Valore di ogni calciatore: percentili per stagione nel ruolo, poi pesi, poi curva."""
    percentiles = {slot: season_percentiles(inputs, slot) for slot in _SLOTS}
    result: dict[Hashable, Valuation] = {}
    for item in inputs:
        current_appearances = item.current.appearances if item.current is not None else 0
        if item.current is None or not item.current.usable:
            current_appearances = 0
        weights = season_weights(current_appearances)
        slot_percentile = {slot: percentiles[slot].get(item.key) for slot in _SLOTS}
        index = (
            weights.current * (slot_percentile["current"] or 0.0)
            + weights.previous * _or_missing(slot_percentile["previous"])
            + weights.two_seasons_ago * _or_missing(slot_percentile["twoSeasonsAgo"])
        )
        result[item.key] = Valuation(
            key=item.key,
            role=item.role,
            value_index=index,
            reference_value=value_curve(index, item.role),
            weights=weights,
            percentiles=slot_percentile,
            has_history=any(value is not None for value in slot_percentile.values()),
        )
    return result


def _or_missing(value: float | None) -> float:
    return MISSING_SEASON_INDEX if value is None else value
