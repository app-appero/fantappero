"""Formazione automatica IA: determinismo e regole anti-vantaggio (EP13-P05)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from database.enums import FantasyRole
from fantasy_lineups.ai_selection import (
    AI_LINEUP_ALGORITHM_VERSION,
    WEIGHT_OFFICIAL_STARTER,
    WEIGHT_RECENT_FORM,
    CandidateInput,
    ExclusionReason,
    SignalSource,
    build_lineup_plan,
    is_eligible,
    official_starter_signal,
    score_candidate,
)

DECIDED_AT = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)

#: 4-3-3 ridotto per i test: un portiere, due difensori, un centrocampista.
SMALL_TARGETS = [
    (FantasyRole.P, 1),
    (FantasyRole.D, 2),
    (FantasyRole.C, 1),
]


def candidate(
    seed: int,
    *,
    role: FantasyRole = FantasyRole.C,
    injured: bool = False,
    official_starter: bool | None = None,
    recent_form: float | None = None,
    recent_appearances: int = 0,
    has_fixture: bool = True,
    kickoff_locked: bool = False,
) -> CandidateInput:
    return CandidateInput(
        athlete_id=UUID(int=seed),
        role=role,
        injured=injured,
        official_starter=official_starter,
        recent_form=recent_form,
        recent_appearances=recent_appearances,
        has_fixture=has_fixture,
        kickoff_locked=kickoff_locked,
    )


# ---------------------------------------------------------------------------
# Eleggibilità
# ---------------------------------------------------------------------------


def test_injured_player_is_excluded_not_penalised() -> None:
    """Schierare un infortunato è un errore, non una scelta rischiosa."""
    assert is_eligible(candidate(1, injured=True)) is ExclusionReason.INJURED


def test_player_without_a_fixture_is_excluded() -> None:
    assert is_eligible(candidate(1, has_fixture=False)) is ExclusionReason.NO_FIXTURE


def test_player_whose_match_started_is_excluded() -> None:
    assert is_eligible(candidate(1, kickoff_locked=True)) is ExclusionReason.KICKOFF_LOCKED


def test_available_player_is_eligible() -> None:
    assert is_eligible(candidate(1)) is None


# ---------------------------------------------------------------------------
# Formula
# ---------------------------------------------------------------------------


def test_official_starter_weighs_double_the_form() -> None:
    """ADR-0005: un titolare mediocre rende più di un fuoriclasse in panchina."""
    starter, _ = score_candidate(candidate(1, official_starter=True, recent_form=0.0))
    in_form, _ = score_candidate(candidate(2, official_starter=False, recent_form=1.0))
    assert starter == WEIGHT_OFFICIAL_STARTER
    assert in_form == WEIGHT_RECENT_FORM
    assert starter > in_form


def test_score_combines_both_signals() -> None:
    value, sources = score_candidate(candidate(1, official_starter=True, recent_form=6.5))
    assert value == WEIGHT_OFFICIAL_STARTER + WEIGHT_RECENT_FORM * 6.5
    assert SignalSource.OFFICIAL_LINEUP in sources
    assert SignalSource.RECENT_FORM in sources


def test_missing_signals_fall_back_without_crashing() -> None:
    value, sources = score_candidate(candidate(1))
    assert value == 0.0
    assert sources == (SignalSource.LOCAL_FALLBACK,)


def test_known_bench_player_still_records_the_official_signal() -> None:
    """Sapere che NON è titolare è informazione, non assenza di informazione."""
    value, sources = score_candidate(candidate(1, official_starter=False))
    assert value == 0.0
    assert SignalSource.OFFICIAL_LINEUP in sources


# ---------------------------------------------------------------------------
# Regola anti-vantaggio sulla distinta ufficiale
# ---------------------------------------------------------------------------


def test_official_lineup_fetched_after_the_decision_is_refused() -> None:
    """Il punto centrale della card: nessun dato successivo alla decisione."""
    assert (
        official_starter_signal(
            is_starter=True,
            fetched_at=DECIDED_AT + timedelta(minutes=1),
            decided_at=DECIDED_AT,
            athlete_kickoff_locked=False,
        )
        is None
    )


def test_official_lineup_fetched_before_the_decision_is_accepted() -> None:
    assert (
        official_starter_signal(
            is_starter=True,
            fetched_at=DECIDED_AT - timedelta(minutes=30),
            decided_at=DECIDED_AT,
            athlete_kickoff_locked=False,
        )
        is True
    )


def test_official_lineup_without_provenance_is_refused() -> None:
    """Senza `fetched_at` non possiamo dimostrare nulla: il segnale non vale."""
    assert (
        official_starter_signal(
            is_starter=True,
            fetched_at=None,
            decided_at=DECIDED_AT,
            athlete_kickoff_locked=False,
        )
        is None
    )


def test_official_lineup_is_refused_once_the_player_is_locked() -> None:
    assert (
        official_starter_signal(
            is_starter=True,
            fetched_at=DECIDED_AT - timedelta(hours=1),
            decided_at=DECIDED_AT,
            athlete_kickoff_locked=True,
        )
        is None
    )


def test_signal_at_the_exact_decision_instant_is_accepted() -> None:
    assert (
        official_starter_signal(
            is_starter=False,
            fetched_at=DECIDED_AT,
            decided_at=DECIDED_AT,
            athlete_kickoff_locked=False,
        )
        is False
    )


# ---------------------------------------------------------------------------
# Costruzione della formazione
# ---------------------------------------------------------------------------


def full_pool() -> list[CandidateInput]:
    return [
        candidate(1, role=FantasyRole.P, official_starter=True, recent_form=6.0),
        candidate(2, role=FantasyRole.P, recent_form=5.0),
        candidate(3, role=FantasyRole.D, official_starter=True, recent_form=6.5),
        candidate(4, role=FantasyRole.D, official_starter=True, recent_form=6.0),
        candidate(5, role=FantasyRole.D, recent_form=5.5),
        candidate(6, role=FantasyRole.C, official_starter=True, recent_form=7.0),
        candidate(7, role=FantasyRole.C, recent_form=6.0),
    ]


def test_plan_respects_role_targets() -> None:
    plan = build_lineup_plan(full_pool(), SMALL_TARGETS, decided_at=DECIDED_AT)
    assert len(plan.starters) == 4
    assert plan.algorithm_version == AI_LINEUP_ALGORITHM_VERSION
    assert plan.unfilled_roles == ()


def test_plan_picks_the_highest_scoring_players_per_role() -> None:
    plan = build_lineup_plan(full_pool(), SMALL_TARGETS, decided_at=DECIDED_AT)
    # Portiere titolare, i due difensori titolari, il centrocampista titolare.
    assert set(plan.starters) == {UUID(int=1), UUID(int=3), UUID(int=4), UUID(int=6)}


def test_plan_is_deterministic_regardless_of_input_order() -> None:
    pool = full_pool()
    first = build_lineup_plan(pool, SMALL_TARGETS, decided_at=DECIDED_AT)
    second = build_lineup_plan(list(reversed(pool)), SMALL_TARGETS, decided_at=DECIDED_AT)
    assert first.starters == second.starters
    assert first.bench == second.bench


def test_ties_are_broken_by_appearances_then_id() -> None:
    pool = [
        candidate(10, role=FantasyRole.C, recent_form=6.0, recent_appearances=1),
        candidate(11, role=FantasyRole.C, recent_form=6.0, recent_appearances=5),
        candidate(12, role=FantasyRole.C, recent_form=6.0, recent_appearances=5),
    ]
    plan = build_lineup_plan(pool, [(FantasyRole.C, 1)], decided_at=DECIDED_AT)
    # Più presenze vince; a parità, id minore.
    assert plan.starters == (UUID(int=11),)


def test_injured_players_never_reach_the_pitch() -> None:
    pool = [
        candidate(20, role=FantasyRole.C, official_starter=True, recent_form=9.0, injured=True),
        candidate(21, role=FantasyRole.C, recent_form=5.0),
    ]
    plan = build_lineup_plan(pool, [(FantasyRole.C, 1)], decided_at=DECIDED_AT)
    assert plan.starters == (UUID(int=21),)
    excluded = {item.athlete_id: item.excluded_reason for item in plan.candidates}
    assert excluded[UUID(int=20)] is ExclusionReason.INJURED


def test_every_candidate_carries_a_reason_when_left_out() -> None:
    """Senza motivo registrato la scelta non è contestabile."""
    pool = [
        candidate(30, role=FantasyRole.C, recent_form=7.0),
        candidate(31, role=FantasyRole.C, recent_form=6.0),
        candidate(32, role=FantasyRole.C, recent_form=5.0),
    ]
    plan = build_lineup_plan(pool, [(FantasyRole.C, 1)], decided_at=DECIDED_AT, bench_size=1)
    left_out = [item for item in plan.candidates if item.athlete_id == UUID(int=32)]
    assert left_out[0].excluded_reason is ExclusionReason.NOT_SELECTED


def test_insufficient_roster_reports_unfilled_roles_instead_of_faking_them() -> None:
    pool = [candidate(40, role=FantasyRole.C, recent_form=6.0)]
    plan = build_lineup_plan(pool, SMALL_TARGETS, decided_at=DECIDED_AT)
    assert plan.is_complete is False
    assert FantasyRole.P in plan.unfilled_roles
    assert FantasyRole.D in plan.unfilled_roles


def test_plan_without_any_provider_signal_still_fields_a_valid_side() -> None:
    """Una formazione mediocre è meglio di nessuna formazione (ADR-0005 §5)."""
    pool = [candidate(50 + i, role=FantasyRole.C) for i in range(3)]
    plan = build_lineup_plan(pool, [(FantasyRole.C, 2)], decided_at=DECIDED_AT)
    assert len(plan.starters) == 2
    assert plan.used_fallback is True


def test_bench_is_ordered_by_score() -> None:
    pool = [
        candidate(60, role=FantasyRole.C, recent_form=7.0),
        candidate(61, role=FantasyRole.C, recent_form=6.0),
        candidate(62, role=FantasyRole.C, recent_form=5.0),
    ]
    plan = build_lineup_plan(pool, [(FantasyRole.C, 1)], decided_at=DECIDED_AT)
    assert plan.bench == (UUID(int=61), UUID(int=62))


def test_bench_size_is_capped_when_requested() -> None:
    pool = [candidate(70 + i, role=FantasyRole.C, recent_form=float(9 - i)) for i in range(5)]
    plan = build_lineup_plan(pool, [(FantasyRole.C, 1)], decided_at=DECIDED_AT, bench_size=2)
    assert len(plan.bench) == 2


def test_locked_player_is_not_moved_into_the_starting_eleven() -> None:
    pool = [
        candidate(
            80, role=FantasyRole.C, official_starter=True, recent_form=9.0, kickoff_locked=True
        ),
        candidate(81, role=FantasyRole.C, recent_form=4.0),
    ]
    plan = build_lineup_plan(pool, [(FantasyRole.C, 1)], decided_at=DECIDED_AT)
    assert plan.starters == (UUID(int=81),)


@pytest.mark.parametrize("size", [0, 1, 3])
def test_empty_or_small_pools_do_not_crash(size: int) -> None:
    pool = [candidate(90 + i, role=FantasyRole.C) for i in range(size)]
    plan = build_lineup_plan(pool, [(FantasyRole.C, 2)], decided_at=DECIDED_AT)
    assert len(plan.starters) == min(size, 2)
