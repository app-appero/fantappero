"""Scelta del modulo migliore per "applica la formazione migliore" (TASK 10).

``select_best_module`` è la parte pura (niente sessione, niente rosa reale)
della modalità ``best_module``: riceve un piano già calcolato per ciascun
modulo candidato e sceglie quello con il punteggio totale più alto tra gli
undici titolari, solo tra i piani completabili con la rosa attuale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from database.enums import FantasyModule, FantasyRole
from fantasy_lineups.ai_selection import LineupPlan, ScoredCandidate
from fantasy_lineups.best_lineup_service import select_best_module

DECIDED_AT = datetime(2026, 10, 26, 18, 0, tzinfo=UTC)


def _eleven_ids() -> tuple[UUID, ...]:
    return tuple(uuid4() for _ in range(11))


def _complete_plan(starter_scores: dict[UUID, float]) -> LineupPlan:
    """Un piano "completo" (11 titolari, nessun ruolo scoperto) con un
    punteggio noto per ciascun titolare."""
    assert len(starter_scores) == 11
    candidates = tuple(
        ScoredCandidate(
            athlete_id=athlete_id,
            role=FantasyRole.C,
            score=score,
            sources=(),
            excluded_reason=None,
        )
        for athlete_id, score in starter_scores.items()
    )
    return LineupPlan(
        algorithm_version="ai_lineup_v1",
        decided_at=DECIDED_AT,
        starters=tuple(starter_scores),
        bench=(),
        candidates=candidates,
        used_fallback=False,
        unfilled_roles=(),
    )


def _incomplete_plan(starter_scores: dict[UUID, float]) -> LineupPlan:
    """Un piano che non raggiunge gli undici titolari: un ruolo resta scoperto."""
    candidates = tuple(
        ScoredCandidate(
            athlete_id=athlete_id,
            role=FantasyRole.C,
            score=score,
            sources=(),
            excluded_reason=None,
        )
        for athlete_id, score in starter_scores.items()
    )
    return LineupPlan(
        algorithm_version="ai_lineup_v1",
        decided_at=DECIDED_AT,
        starters=tuple(starter_scores),
        bench=(),
        candidates=candidates,
        used_fallback=False,
        unfilled_roles=(FantasyRole.A,),
    )


def test_picks_the_complete_plan_with_the_highest_starter_score() -> None:
    weak_ids = _eleven_ids()
    strong_ids = _eleven_ids()
    weak_plan = _complete_plan({athlete_id: 5.0 for athlete_id in weak_ids})
    strong_plan = _complete_plan({athlete_id: 7.0 for athlete_id in strong_ids})

    result = select_best_module(
        [(FantasyModule.M343, weak_plan), (FantasyModule.M433, strong_plan)]
    )
    assert result is not None
    module, plan = result
    assert module is FantasyModule.M433
    assert plan is strong_plan


def test_incomplete_plans_are_never_selected_even_with_a_higher_raw_score() -> None:
    """Un modulo che non si riesce a completare con la rosa (ruolo scoperto)
    non va mai scelto, anche se la somma punteggio dei pochi titolari
    assegnati fosse più alta di un piano completo ma più modesto."""
    complete_ids = _eleven_ids()
    complete_plan = _complete_plan({athlete_id: 1.0 for athlete_id in complete_ids})
    incomplete_plan = _incomplete_plan({uuid4(): 99.0, uuid4(): 99.0})

    result = select_best_module(
        [(FantasyModule.M352, incomplete_plan), (FantasyModule.M541, complete_plan)]
    )
    assert result is not None
    module, plan = result
    assert module is FantasyModule.M541
    assert plan is complete_plan


def test_ties_break_on_the_lexicographically_smaller_module_code() -> None:
    ids_a = _eleven_ids()
    ids_b = _eleven_ids()
    plan_a = _complete_plan({athlete_id: 4.0 for athlete_id in ids_a})
    plan_b = _complete_plan({athlete_id: 4.0 for athlete_id in ids_b})

    # "3-4-3" < "4-4-2" lessicograficamente.
    result = select_best_module([(FantasyModule.M442, plan_b), (FantasyModule.M343, plan_a)])
    assert result is not None
    module, _plan = result
    assert module is FantasyModule.M343


def test_no_complete_plan_returns_none() -> None:
    incomplete_plan = _incomplete_plan({uuid4(): 10.0})
    assert select_best_module([(FantasyModule.M433, incomplete_plan)]) is None


def test_empty_plan_list_returns_none() -> None:
    assert select_best_module([]) is None


def test_only_the_chosen_starters_count_towards_the_score() -> None:
    """Un bloccato retrocesso in panchina (bench) non deve pesare sul
    punteggio totale del modulo: solo chi resta tra i titolari conta."""
    starters = _eleven_ids()
    bench_only = uuid4()
    candidates = tuple(
        ScoredCandidate(
            athlete_id=aid, role=FantasyRole.C, score=1.0, sources=(), excluded_reason=None
        )
        for aid in starters
    ) + (
        ScoredCandidate(
            athlete_id=bench_only,
            role=FantasyRole.C,
            score=1000.0,
            sources=(),
            excluded_reason=None,
        ),
    )
    plan_with_bench_outlier = LineupPlan(
        algorithm_version="ai_lineup_v1",
        decided_at=DECIDED_AT,
        starters=starters,
        bench=(bench_only,),
        candidates=candidates,
        used_fallback=False,
        unfilled_roles=(),
    )
    other_ids = _eleven_ids()
    other_plan = _complete_plan({athlete_id: 2.0 for athlete_id in other_ids})

    result = select_best_module(
        [
            (FantasyModule.M433, plan_with_bench_outlier),  # score reale: 11.0
            (FantasyModule.M442, other_plan),  # score: 22.0
        ]
    )
    assert result is not None
    module, _plan = result
    assert module is FantasyModule.M442
