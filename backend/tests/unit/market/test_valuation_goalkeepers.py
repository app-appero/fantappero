"""Portieri e Valore: cosa fa la formula di oggi con dati sintetici (domanda di Rosario, 23/11).

Domande:

1. un portiere con medie intorno a 6,7–7,0 in tutte e tre le stagioni finisce vicino al valore
   base del ruolo?
2. se i voti del fornitore delle serie minori (es. Segunda) sono sistematicamente più alti di
   quelli della Premier, i portieri che vengono da lì superano i portieri top?

Nessuna chiamata al fornitore, nessun database: un listone di portieri simulato e la formula di
``market.valuation`` con le costanti di oggi (non si cambiano qui). Ipotesi della simulazione
(``goalkeeper_pool``), dichiarate perché i numeri dipendono da loro:

- stagioni passate (media del fornitore, ``games.rating``): titolari dei 5 campionati
  N(6,90; 0,18) con 26–38 presenze; riserve N(6,80; 0,35) con 1–8 presenze, metà senza presenze
  in una stagione; portieri dalle serie minori N(6,90 + scarto; 0,18) con 30–42 presenze;
- stagione in corso (nostri voti, 12 giornate): titolari N(6,66; 0,18) con 9–12 voti — 6,66 è la
  media del voto dei portieri nel report ``experiments/rating_beta`` (beta-v0.1); un quarto
  delle riserve con 1–3 voti.

Per rivedere i numeri (la tabella che finisce nel report a Rosario)::

    cd backend && PYTHONPATH=src python tests/unit/market/test_valuation_goalkeepers.py
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

from market.valuation import (
    SeasonSample,
    Valuation,
    ValuationInput,
    base_reference_value,
    compute_valuations,
    credits_for_budget,
    value_curve,
)

SEED = 20261123
TOP_KEEPERS = 88
PROMOTED_KEEPERS = 8  # dalle serie minori, oggi titolari nelle neopromosse
LOWER_DIVISION_BACKUPS = 7  # dalle serie minori, oggi riserve
BACKUPS = 185

PROVIDER_STARTER_MEAN = 6.90
PROVIDER_STARTER_SD = 0.18
OUR_STARTER_MEAN = 6.66
OUR_STARTER_SD = 0.18
CURRENT_VOTES = 12


@dataclass(frozen=True)
class Subject:
    """Un portiere da valutare: medie (presenze) della stagione in corso, scorsa e due fa."""

    key: str
    label: str
    current: tuple[float, int] | None
    previous: tuple[float, int] | None
    two_seasons_ago: tuple[float, int] | None

    def as_input(self) -> ValuationInput:
        def sample(value: tuple[float, int] | None) -> SeasonSample | None:
            return SeasonSample(*value) if value is not None else None

        return ValuationInput(
            key=self.key,
            role="P",
            current=sample(self.current),
            previous=sample(self.previous),
            two_seasons_ago=sample(self.two_seasons_ago),
        )


SUBJECTS = (
    Subject("donnarumma", "Donnarumma (6,68 / 7,03 / 6,86)", (6.68, 12), (7.03, 34), (6.86, 36)),
    # Lo stesso se le due stagioni passate non contassero (es. righe senza media o non di
    # campionato): è la stagione in corso, da sola, a decidere.
    Subject("donnarumma_no_past", "Donnarumma senza stagioni passate", (6.68, 12), None, None),
    Subject("flat_670", "Costante 6,70", (6.70, 12), (6.70, 34), (6.70, 34)),
    Subject("flat_685", "Costante 6,85", (6.85, 12), (6.85, 34), (6.85, 34)),
    Subject("flat_700", "Costante 7,00", (7.00, 12), (7.00, 34), (7.00, 34)),
    # Titolare di una squadra dominante: pochi tiri, poche parate, voti nella media.
    Subject(
        "dominant_team",
        "Top di squadra dominante (6,50 / 6,95 / 6,95)",
        (6.50, 12),
        (6.95, 34),
        (6.95, 34),
    ),
    # Dalla Segunda: 7,75 nella 2025/26 e 7,40 nella 2024/25, oggi titolare in Liga.
    Subject(
        "cunat", "Cuñat (6,90 / 7,75 Segunda / 7,40 Segunda)", (6.90, 12), (7.75, 40), (7.40, 38)
    ),
)


def goalkeeper_pool(rng: random.Random, *, lower_division_offset: float) -> list[ValuationInput]:
    """I portieri del listone, tranne i soggetti (ipotesi nel docstring del modulo)."""

    def provider(mean: float, sd: float, low: int, high: int) -> SeasonSample:
        return SeasonSample(rng.gauss(mean, sd), rng.randint(low, high))

    def ours(mean: float, sd: float, low: int, high: int) -> SeasonSample:
        return SeasonSample(rng.gauss(mean, sd), rng.randint(low, high))

    pool: list[ValuationInput] = []
    for index in range(TOP_KEEPERS):
        pool.append(
            ValuationInput(
                key=f"top_{index}",
                role="P",
                current=ours(OUR_STARTER_MEAN, OUR_STARTER_SD, 9, CURRENT_VOTES),
                previous=provider(PROVIDER_STARTER_MEAN, PROVIDER_STARTER_SD, 26, 38),
                two_seasons_ago=provider(PROVIDER_STARTER_MEAN, PROVIDER_STARTER_SD, 26, 38),
            )
        )
    lower_mean = PROVIDER_STARTER_MEAN + lower_division_offset
    for index in range(PROMOTED_KEEPERS + LOWER_DIVISION_BACKUPS):
        starter_now = index < PROMOTED_KEEPERS
        pool.append(
            ValuationInput(
                key=f"lower_{index}",
                role="P",
                current=ours(OUR_STARTER_MEAN, OUR_STARTER_SD, 9, CURRENT_VOTES)
                if starter_now
                else None,
                previous=provider(lower_mean, PROVIDER_STARTER_SD, 30, 42),
                two_seasons_ago=provider(lower_mean, PROVIDER_STARTER_SD, 30, 42),
            )
        )
    for index in range(BACKUPS):

        def backup_season() -> SeasonSample | None:
            if rng.random() < 0.5:
                return None
            return provider(6.80, 0.35, 1, 8)

        pool.append(
            ValuationInput(
                key=f"backup_{index}",
                role="P",
                current=ours(6.60, 0.40, 1, 3) if rng.random() < 0.25 else None,
                previous=backup_season(),
                two_seasons_ago=backup_season(),
            )
        )
    return pool


def simulate(*, lower_division_offset: float, seed: int = SEED) -> dict[str, Valuation]:
    pool = goalkeeper_pool(random.Random(seed), lower_division_offset=lower_division_offset)
    return compute_valuations([*pool, *(subject.as_input() for subject in SUBJECTS)])


def credits(valuation: Valuation, budget: int = 1000) -> int:
    return credits_for_budget(valuation.reference_value, budget)


@dataclass(frozen=True)
class Scenario:
    """Risultato su ``SEEDS`` listoni simulati (mediane e medie: numeri stabili)."""

    lower_division_offset: float
    #: Crediti a budget 1000 di ogni soggetto: mediana sui listoni.
    subject_credits: dict[str, float]
    #: Percentili (in corso, scorsa, due fa) e p di ogni soggetto: mediana sui listoni.
    subject_percentiles: dict[str, tuple[float | None, float | None, float | None]]
    subject_index: dict[str, float]
    #: Crediti medi dei portieri dalle serie minori oggi titolari e dei titolari dei 5.
    promoted_mean: float
    top_mean: float


SEEDS = range(1, 21)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def scenario(lower_division_offset: float) -> Scenario:
    runs = [simulate(lower_division_offset=lower_division_offset, seed=seed) for seed in SEEDS]
    keys = [subject.key for subject in SUBJECTS]

    def median_percentile(key: str, slot: str) -> float | None:
        values = [run[key].percentiles[slot] for run in runs]
        known = [value for value in values if value is not None]
        return _median(known) if known else None

    promoted = [run[f"lower_{i}"].reference_value for run in runs for i in range(PROMOTED_KEEPERS)]
    top = [run[f"top_{i}"].reference_value for run in runs for i in range(TOP_KEEPERS)]
    return Scenario(
        lower_division_offset=lower_division_offset,
        subject_credits={key: _median([credits(run[key]) for run in runs]) for key in keys},
        subject_percentiles={
            key: (
                median_percentile(key, "current"),
                median_percentile(key, "previous"),
                median_percentile(key, "twoSeasonsAgo"),
            )
            for key in keys
        },
        subject_index={key: _median([run[key].value_index for run in runs]) for key in keys},
        promoted_mean=sum(promoted) / len(promoted),
        top_mean=sum(top) / len(top),
    )


# -- test ---------------------------------------------------------------------------------------


def test_median_goalkeeper_is_worth_a_fifth_of_the_top() -> None:
    # La curva convessa: al 50° percentile combinato un portiere vale 6,5 crediti su 30.
    assert value_curve(0.5, "P") == pytest.approx(6.49, abs=0.01)
    assert credits_for_budget(base_reference_value("P"), 1000) == 3
    assert credits_for_budget(value_curve(0.8, "P"), 1000) == 18


def test_goalkeeper_around_670_stays_near_the_base_value() -> None:
    neutral = scenario(0.0).subject_credits
    base = credits_for_budget(base_reference_value("P"), 1000)
    assert abs(neutral["flat_670"] - base) <= 1
    # Pochi decimi di media spostano molto: 6,70 → 7,00 in tutte le stagioni.
    assert neutral["flat_700"] >= 5 * neutral["flat_670"]
    # Donnarumma con questi dati non scende al valore base: un 3 vuol dire dati diversi (stagione
    # non contata, percentili bassi): lo dice il «Dettaglio del Valore».
    assert neutral["donnarumma"] >= base + 5
    # Un portiere top di squadra dominante (poche parate) vale poco più della base.
    assert neutral["dominant_team"] <= base + 4


def test_higher_lower_division_ratings_push_those_keepers_above_top_keepers() -> None:
    neutral = scenario(0.0)
    inflated = scenario(0.30)

    # A parità di livello i due gruppi valgono più o meno uguale; con voti più alti di 0,30
    # nelle serie minori chi viene da lì vale circa il doppio dei titolari dei 5 campionati.
    assert neutral.promoted_mean < 1.25 * neutral.top_mean
    assert inflated.promoted_mean > 1.8 * inflated.top_mean
    assert inflated.promoted_mean > 1.6 * neutral.promoted_mean
    # Cuñat (7,75 in Segunda) è fra i portieri più cari, sopra Donnarumma e la squadra dominante.
    cunat = inflated.subject_credits["cunat"]
    assert cunat > 2 * inflated.subject_credits["donnarumma"]
    assert cunat > 3 * inflated.subject_credits["dominant_team"]


# -- report -------------------------------------------------------------------------------------


def _pct(value: float | None) -> str:
    return "  —  " if value is None else f"{value * 100:5.1f}"


def report() -> str:
    lines = [
        f"Portieri, mediane su {len(SEEDS)} listoni simulati: percentile per stagione "
        "(in corso / scorsa / due fa), p, crediti a budget 1000",
        f"Valore base P: {credits_for_budget(base_reference_value('P'), 1000)} crediti; "
        f"p=0,5 → {value_curve(0.5, 'P'):.1f}; p=0,8 → {value_curve(0.8, 'P'):.1f}",
    ]
    for offset in (0.0, 0.15, 0.30):
        result = scenario(offset)
        lines.append("")
        lines.append(
            f"Voti delle serie minori +{offset:.2f}: portieri dalle serie minori oggi titolari "
            f"{result.promoted_mean:.1f} crediti in media, titolari dei 5 campionati "
            f"{result.top_mean:.1f}"
        )
        for subject in SUBJECTS:
            current, previous, two_ago = result.subject_percentiles[subject.key]
            lines.append(
                f"  {subject.label:<48} {_pct(current)} / {_pct(previous)} / {_pct(two_ago)}"
                f"  p={result.subject_index[subject.key]:.3f}"
                f"  → {result.subject_credits[subject.key]:>4.0f} crediti"
            )
    return "\n".join(lines)


if __name__ == "__main__":
    print(report())
