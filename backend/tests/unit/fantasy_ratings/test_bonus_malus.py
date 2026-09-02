"""Unit tests for bonus/malus rules (EP07-03 / FR-SCO-02)."""

from __future__ import annotations

from fantasy_ratings.bonus import (
    BonusMalusInput,
    compute_bonus_malus,
    reconstruct_total_from_stored,
)
from fantasy_ratings.bonus_config import default_bonus_config

CONFIG = default_bonus_config()


def _ids(result) -> set[str]:
    return {item.id for item in result.components}


def test_ineligible_player_gets_no_bonus_malus() -> None:
    data = BonusMalusInput(goals=1, assists=1, yellow_card=True)
    result = compute_bonus_malus(data, CONFIG, eligible=False)
    assert result.eligible is False
    assert result.components == ()
    assert result.total == 0.0


def test_goal_and_assist_multiply_by_count() -> None:
    data = BonusMalusInput(goals=2, assists=1)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.total == 2 * 3.0 + 1 * 1.0
    assert _ids(result) == {"goal", "assist"}


def test_yellow_card_malus() -> None:
    data = BonusMalusInput(yellow_card=True)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.total == -0.5
    assert _ids(result) == {"yellow_card"}


def test_red_card_malus() -> None:
    data = BonusMalusInput(red_card=True)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.total == -1.0
    assert _ids(result) == {"red_card"}


def test_double_yellow_and_red_does_not_double_count() -> None:
    """FR-SCO-02: la seconda ammonizione che produce l'espulsione non deve
    sommare -0,5 e -1: soltanto il malus espulsione viene applicato."""
    data = BonusMalusInput(yellow_card=True, red_card=True)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.total == -1.0
    assert _ids(result) == {"red_card"}


def test_own_goal_malus_scales_with_count() -> None:
    data = BonusMalusInput(own_goals=2)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.total == -4.0


def test_penalty_missed_malus() -> None:
    data = BonusMalusInput(penalty_missed=1)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.total == -3.0


def test_penalty_saved_bonus_only_for_goalkeeper() -> None:
    outfield = BonusMalusInput(penalty_saved=1, role="D")
    result = compute_bonus_malus(outfield, CONFIG, eligible=True)
    assert result.total == 0.0
    assert result.components == ()

    keeper = BonusMalusInput(penalty_saved=1, role="P")
    result = compute_bonus_malus(keeper, CONFIG, eligible=True)
    assert result.total == 3.0
    assert _ids(result) == {"penalty_saved"}


def test_goalkeeper_goals_conceded_malus() -> None:
    data = BonusMalusInput(role="P", team_goals_conceded=2)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.total == -2.0
    assert _ids(result) == {"goalkeeper_goal_conceded"}


def test_goalkeeper_clean_sheet_bonus() -> None:
    data = BonusMalusInput(role="P", team_goals_conceded=0)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.total == 1.0
    assert _ids(result) == {"goalkeeper_clean_sheet"}


def test_goals_conceded_not_applied_outside_goalkeeper_role() -> None:
    """Un difensore con team_goals_conceded=0 non riceve la porta inviolata:
    FR-SCO-02 riserva il bonus al portiere."""
    data = BonusMalusInput(role="D", team_goals_conceded=0)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.components == ()


def test_pending_score_skips_goalkeeper_components() -> None:
    data = BonusMalusInput(role="P", team_goals_conceded=None)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    assert result.components == ()


def test_result_is_reconstructable_from_stored_components() -> None:
    data = BonusMalusInput(goals=1, assists=1, red_card=True, role="P", team_goals_conceded=1)
    result = compute_bonus_malus(data, CONFIG, eligible=True)
    stored = result.as_dict()
    assert reconstruct_total_from_stored(stored) == result.total


def test_idempotent_recomputation() -> None:
    data = BonusMalusInput(goals=1, assists=2, yellow_card=True, role="A")
    first = compute_bonus_malus(data, CONFIG, eligible=True)
    second = compute_bonus_malus(data, CONFIG, eligible=True)
    assert first.as_dict() == second.as_dict()
    assert first.total == second.total
