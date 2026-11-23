"""Valore di mercato e media stagionale (1.3): formule pure di ``market.valuation``.

La tabella ``CANVAS_TABLE`` è la stessa di ``docs/operations/valore_di_mercato_e_storico.md``:
se una costante cambia, cambiano insieme.
"""

from __future__ import annotations

import random

import pytest

from leagues.validators import STANDARD_TOTAL_CREDITS
from market import valuation
from market.valuation import (
    MISSING_SEASON_INDEX,
    REFERENCE_BUDGET,
    SeasonSample,
    ValuationInput,
    base_reference_value,
    combine_rows,
    compute_valuations,
    credits_for_budget,
    mid_rank_percentiles,
    season_percentiles,
    season_positions,
    season_weights,
    select_season_average,
    shrink_rating,
    value_curve,
)
from sports_data.season_stats.seasons import career_seasons, past_seasons, season_label

# -- stagioni -------------------------------------------------------------------------------


def test_season_label_and_past_seasons() -> None:
    assert season_label(2025) == "25/26"
    assert season_label(2026) == "26/27"
    assert season_label(2099) == "99/00"
    assert past_seasons(2026) == (2025, 2024)
    assert career_seasons(2026) == (2026, 2025, 2024)


def test_reference_budget_is_the_league_default() -> None:
    assert REFERENCE_BUDGET == STANDARD_TOTAL_CREDITS == 1000


# -- media stagionale: verde «in corso», rossa «25/26», oppure niente -------------------------


def test_season_average_prefers_current_season_with_at_least_one_vote() -> None:
    average = select_season_average(
        current_season_year=2026,
        current=SeasonSample(rating=6.25, appearances=1),
        previous=SeasonSample(rating=6.91, appearances=30),
    )
    assert average is not None
    assert average.is_current is True
    assert average.value == 6.25
    assert average.season_year == 2026
    assert average.season_label == "26/27"


def test_season_average_falls_back_to_previous_season_from_provider() -> None:
    average = select_season_average(
        current_season_year=2026,
        current=SeasonSample(rating=None, appearances=0),
        previous=SeasonSample(rating=6.912345, appearances=30),
    )
    assert average is not None
    assert average.is_current is False
    assert average.value == 6.91
    assert average.season_year == 2025
    assert average.season_label == "25/26"


def test_season_average_is_none_without_votes_or_previous_rating() -> None:
    assert select_season_average(current_season_year=2026, current=None, previous=None) is None
    assert (
        select_season_average(
            current_season_year=2026,
            current=None,
            previous=SeasonSample(rating=None, appearances=12),  # rating null del fornitore
        )
        is None
    )


def test_combine_rows_weights_a_mid_season_move_by_appearances() -> None:
    sample = combine_rows([(7.0, 10), (6.0, 30), (None, 5)])
    assert sample.appearances == 40
    assert sample.rating == pytest.approx(6.25)
    assert combine_rows([(None, 3)]).usable is False
    # Media senza presenze (dato incompleto): conta come una partita.
    assert combine_rows([(6.5, None)]) == SeasonSample(rating=6.5, appearances=1)


# -- pesi, riduzione, percentili -------------------------------------------------------------


@pytest.mark.parametrize(
    ("appearances", "current", "previous", "two_ago"),
    [
        (0, 0.0, 0.6, 0.4),
        (3, 0.1, 0.54, 0.36),
        (6, 0.2, 0.48, 0.32),
        (15, 0.5, 0.3, 0.2),
        (38, 0.5, 0.3, 0.2),
    ],
)
def test_season_weights_grow_with_current_appearances(
    appearances: int, current: float, previous: float, two_ago: float
) -> None:
    weights = season_weights(appearances)
    assert weights.current == pytest.approx(current)
    assert weights.previous == pytest.approx(previous)
    assert weights.two_seasons_ago == pytest.approx(two_ago)
    assert weights.current + weights.previous + weights.two_seasons_ago == pytest.approx(1.0)


def test_shrink_pulls_few_appearances_toward_the_role_mean() -> None:
    few = shrink_rating(8.0, 3, 6.2)
    many = shrink_rating(7.0, 30, 6.2)
    assert 6.2 < few < 7.0
    assert many > few  # 30 partite da 7 battono 3 partite da 8
    assert shrink_rating(6.2, 0, 6.2) == pytest.approx(6.2)


def test_mid_rank_percentiles() -> None:
    assert mid_rank_percentiles({}) == {}
    assert mid_rank_percentiles({"solo": 6.0}) == {"solo": 0.5}
    result = mid_rank_percentiles({"a": 5.0, "b": 6.0, "c": 6.0, "d": 7.0})
    assert result["a"] == pytest.approx(0.125)
    assert result["b"] == result["c"] == pytest.approx(0.5)
    assert result["d"] == pytest.approx(0.875)


def test_percentile_is_computed_within_role() -> None:
    inputs = [
        ValuationInput(key="d_best", role="D", previous=SeasonSample(6.4, 30)),
        ValuationInput(key="d_worst", role="D", previous=SeasonSample(6.0, 30)),
        ValuationInput(key="a_best", role="A", previous=SeasonSample(7.4, 30)),
        ValuationInput(key="a_worst", role="A", previous=SeasonSample(6.9, 30)),
    ]
    percentiles = season_percentiles(inputs, "previous")
    # Il miglior difensore è primo fra i difensori anche con una media più bassa degli attaccanti.
    assert percentiles["d_best"] == percentiles["a_best"] == pytest.approx(0.75)
    assert percentiles["d_worst"] == percentiles["a_worst"] == pytest.approx(0.25)


def test_provider_scale_and_our_scale_are_compared_by_rank() -> None:
    """Il fornitore dà medie attorno a 6,8, i nostri voti attorno a 6: conta la posizione."""
    inputs = [
        ValuationInput(
            key=f"c{i}",
            role="C",
            current=SeasonSample(5.6 + 0.1 * i, 15),
            previous=SeasonSample(6.5 + 0.1 * i, 30),
            two_seasons_ago=SeasonSample(6.5 + 0.1 * i, 30),
        )
        for i in range(10)
    ]
    result = compute_valuations(inputs)
    best, worst = result["c9"], result["c0"]
    assert best.percentiles["current"] == best.percentiles["previous"] == pytest.approx(0.95)
    assert worst.percentiles["current"] == pytest.approx(0.05)
    assert best.value_index == pytest.approx(0.95)
    assert best.reference_value > 5 * worst.reference_value


def test_three_good_games_do_not_make_a_starter() -> None:
    starters = [
        ValuationInput(
            key=f"s{i}",
            role="A",
            current=SeasonSample(6.4 + 0.05 * i, 15),
            previous=SeasonSample(6.9 + 0.05 * i, 32),
            two_seasons_ago=SeasonSample(6.9 + 0.05 * i, 32),
        )
        for i in range(20)
    ]
    star = ValuationInput(
        key="star",
        role="A",
        current=SeasonSample(7.6, 15),
        previous=SeasonSample(7.0, 32),
        two_seasons_ago=SeasonSample(7.0, 32),
    )
    newcomer = ValuationInput(key="new", role="A", current=SeasonSample(7.9, 3))
    result = compute_valuations([*starters, star, newcomer])
    # Tre partite da 7,9 contano meno di quindici da 7,6: la media ristretta lo mette dietro.
    assert result["new"].percentiles["current"] < result["star"].percentiles["current"]
    # E con il peso basso della stagione in corso vale meno di un titolare medio.
    assert result["new"].reference_value < result["s10"].reference_value
    assert result["new"].reference_value > base_reference_value("A")


def test_season_positions_give_role_mean_shrunk_rank_and_pool_size() -> None:
    inputs = [
        ValuationInput(key="a", role="P", previous=SeasonSample(7.0, 30)),
        ValuationInput(key="b", role="P", previous=SeasonSample(6.5, 10)),
        ValuationInput(key="c", role="P", previous=SeasonSample(6.5, 10)),
        ValuationInput(key="d", role="P", previous=None),
        ValuationInput(key="x", role="A", previous=SeasonSample(8.0, 30)),
    ]
    positions = season_positions(inputs, "previous")
    assert set(positions) == {"a", "b", "c", "x"}  # «d» non ha dati: fuori dal gruppo
    role_mean = (7.0 * 30 + 6.5 * 10 + 6.5 * 10) / 50
    assert positions["a"].role_mean == pytest.approx(role_mean)
    assert positions["a"].shrunk == pytest.approx(shrink_rating(7.0, 30, role_mean))
    assert positions["a"].pool_size == 3
    assert positions["a"].rank == 1
    assert positions["b"].rank == positions["c"].rank == 2  # pari merito
    assert positions["b"].percentile == pytest.approx(1 / 3)
    assert positions["x"].pool_size == 1 and positions["x"].rank == 1


def test_components_explain_every_step_of_the_value() -> None:
    inputs = [
        ValuationInput(
            key=f"p{i}",
            role="P",
            current=SeasonSample(6.2 + 0.05 * i, 6),
            previous=SeasonSample(6.7 + 0.04 * i, 30),
        )
        for i in range(10)
    ]
    valued = compute_valuations(inputs)["p7"]
    components = valued.components()
    seasons = components["seasons"]
    assert list(seasons) == ["current", "previous", "twoSeasonsAgo"]
    current, previous, two_ago = seasons["current"], seasons["previous"], seasons["twoSeasonsAgo"]
    assert current["hasData"] is True
    assert current["appearances"] == 6
    assert current["average"] == pytest.approx(6.55)
    assert current["poolSize"] == 10 and current["rank"] == 3
    assert current["percentile"] == pytest.approx(0.75)
    assert current["weight"] == pytest.approx(0.5 * 6 / 15)
    assert previous["shrunkAverage"] == pytest.approx(
        shrink_rating(6.98, 30, previous["roleAverage"]), abs=1e-3
    )
    # Stagione senza dati: indice 0,33 con il suo peso.
    assert two_ago["hasData"] is False
    assert two_ago["indexUsed"] == pytest.approx(MISSING_SEASON_INDEX)
    assert two_ago["percentile"] is None and two_ago["poolSize"] is None
    # Dai passaggi salvati si rifà il numero: somma dei contributi = p, poi la curva.
    assert sum(season["contribution"] for season in seasons.values()) == pytest.approx(
        components["valueIndex"], abs=1e-3
    )
    assert components["referenceValue"] == pytest.approx(
        components["floor"]
        + (components["roleTop"] - components["floor"])
        * components["valueIndex"] ** components["curveExponent"],
        abs=1e-3,
    )
    assert components["roleTop"] == valuation.TOP_REFERENCE_CREDITS["P"]
    assert components["referenceBudget"] == REFERENCE_BUDGET
    # I campi della 1.3 restano.
    assert components["percentiles"]["previous"] == previous["percentile"]
    assert components["weights"]["current"] == current["weight"]


def test_no_history_gets_the_base_value_of_the_role() -> None:
    result = compute_valuations([ValuationInput(key=role, role=role) for role in "PDCA"])
    for role in "PDCA":
        assert result[role].has_history is False
        assert result[role].value_index == pytest.approx(MISSING_SEASON_INDEX)
        assert result[role].reference_value == pytest.approx(base_reference_value(role))
    assert [credits_for_budget(base_reference_value(r), 1000) for r in "PDCA"] == [3, 3, 4, 6]


def test_value_curve_is_convex_and_bounded() -> None:
    for role, top in valuation.TOP_REFERENCE_CREDITS.items():
        assert value_curve(0.0, role) == pytest.approx(valuation.FLOOR_REFERENCE_CREDITS)
        assert value_curve(1.0, role) == pytest.approx(top)
        assert value_curve(1.5, role) == pytest.approx(top)
        # Convessa: da 0,5 a 1 si guadagna molto più che da 0 a 0,5.
        low = value_curve(0.5, role) - value_curve(0.0, role)
        high = value_curve(1.0, role) - value_curve(0.5, role)
        assert high > 3 * low


@pytest.mark.parametrize(
    ("reference", "budget", "credits"),
    [
        (58.47, 1000, 58),
        (58.47, 500, 29),
        (58.47, 2000, 117),
        (3.03, 300, 1),  # mai sotto 1 credito
        (0.2, 1000, 1),
    ],
)
def test_credits_are_proportional_to_the_league_budget(
    reference: float, budget: int, credits: int
) -> None:
    assert credits_for_budget(reference, budget) == credits


# -- tabella degli esempi (canvas «Proposte 1.3», budget standard 1000) -----------------------

#: (caso, ruolo, indice combinato, crediti a 1000, crediti a 500)
CANVAS_TABLE = [
    ("Attaccante titolare nel top 5%", "A", 0.95, 58, 29),
    ("Centrocampista di rotazione medio", "C", 0.545, 12, 6),
    ("Nuovo arrivato con 3 belle partite", "A", 0.389, 8, 4),
    ("Attaccante senza storico (base)", "A", MISSING_SEASON_INDEX, 6, 3),
    ("Centrocampista senza storico (base)", "C", MISSING_SEASON_INDEX, 4, 2),
    ("Difensore senza storico (base)", "D", MISSING_SEASON_INDEX, 3, 2),
    ("Portiere senza storico (base)", "P", MISSING_SEASON_INDEX, 3, 2),
    ("Portiere titolare nel top 5%", "P", 0.95, 27, 13),
    ("Difensore titolare nel top 5%", "D", 0.95, 28, 14),
    ("Centrocampista titolare nel top 5%", "C", 0.95, 43, 21),
]


@pytest.mark.parametrize(("case", "role", "index", "at_1000", "at_500"), CANVAS_TABLE)
def test_canvas_example_table(
    case: str, role: str, index: float, at_1000: int, at_500: int
) -> None:
    reference = value_curve(index, role)
    assert credits_for_budget(reference, 1000) == at_1000, case
    assert credits_for_budget(reference, 500) == at_500, case


def _synthetic_listone(seed: int = 7) -> list[ValuationInput]:
    """Listone verosimile: titolari, rotazioni e riserve per ruolo, alla 12ª giornata."""
    rng = random.Random(seed)
    items: list[ValuationInput] = []
    for role, count in (("P", 180), ("D", 800), ("C", 800), ("A", 520)):
        for index in range(count):
            tier = rng.random()
            if tier < 0.35:
                apps, apps2, quality = rng.randint(26, 36), rng.randint(24, 36), 0.4
                votes = rng.randint(9, 12)
            elif tier < 0.7:
                apps, apps2, quality = rng.randint(12, 25), rng.randint(10, 25), 0.0
                votes = rng.randint(3, 8)
            else:
                apps, apps2, quality = rng.randint(1, 11), rng.randint(1, 11), -0.4
                votes = rng.randint(0, 4)
            q = rng.gauss(quality, 0.8)
            items.append(
                ValuationInput(
                    key=f"{role}{index}",
                    role=role,
                    current=SeasonSample(6.05 + 0.3 * q + rng.gauss(0, 0.25), votes)
                    if votes
                    else None,
                    previous=SeasonSample(6.75 + 0.25 * q + rng.gauss(0, 0.12), apps),
                    two_seasons_ago=SeasonSample(6.75 + 0.25 * q + rng.gauss(0, 0.12), apps2),
                )
            )
    return items


def _rating_at(items: list[ValuationInput], role: str, slot: str, quantile: float) -> float:
    values = sorted(
        getattr(item, slot).rating
        for item in items
        if item.role == role and getattr(item, slot) is not None
    )
    return values[int(quantile * (len(values) - 1))]


def test_canvas_examples_on_a_realistic_listone() -> None:
    listone = _synthetic_listone()
    mid_rotation = ValuationInput(
        key="mid_rotation_midfielder",
        role="C",
        current=SeasonSample(_rating_at(listone, "C", "current", 0.55), 7),
        previous=SeasonSample(_rating_at(listone, "C", "previous", 0.55), 19),
        two_seasons_ago=SeasonSample(_rating_at(listone, "C", "two_seasons_ago", 0.55), 21),
    )
    newcomer = ValuationInput(key="newcomer", role="A", current=SeasonSample(7.0, 3))
    top_forward = ValuationInput(
        key="top_forward",
        role="A",
        current=SeasonSample(_rating_at(listone, "A", "current", 0.95), 12),
        previous=SeasonSample(_rating_at(listone, "A", "previous", 0.95), 34),
        two_seasons_ago=SeasonSample(_rating_at(listone, "A", "two_seasons_ago", 0.95), 33),
    )
    result = compute_valuations([*listone, mid_rotation, newcomer, top_forward])

    def credits(key: str) -> int:
        return credits_for_budget(result[key].reference_value, 1000)

    assert 55 <= credits("top_forward") <= 64  # canvas ≈ 58
    assert 10 <= credits("mid_rotation_midfielder") <= 14  # canvas ≈ 12
    assert 7 <= credits("newcomer") <= 9  # canvas ≈ 8
    assert credits("top_forward") > 4 * credits("mid_rotation_midfielder")
