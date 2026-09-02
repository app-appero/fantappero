"""Motore unico di calcolo turno (EP-turni-calcolo).

Un solo punto di ingresso, `calculate_league_round`, chiamato sia dal job
automatico (`fantasy_turns.live_pipeline.process_live_fantasy_rounds`) sia
dai comandi manuali del pannello di controllo (globale, per-lega, e
riparazione storico) — stessa identica logica in tutti e quattro i casi,
nessuna implementazione divergente.

Ordine: rating delle fixture con nuove statistiche -> se il turno è concluso,
garantisce una formazione per ogni squadra (bozza / ultima valida / 0 punti,
vedi `fantasy_lineups.fallback_service`) -> formazioni effettive -> risultati
H2H (che aggiornano la classifica in modo incondizionato, già così) ->
omologazione condizionale.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from fantasy_lineups.fallback_service import (
    LineupFallbackResult,
    ensure_lineup_submissions_for_round,
)
from fantasy_lineups.substitution_service import compute_round_effective_lineups
from fantasy_ratings.service import compute_fixture_ratings
from fantasy_turns.homologation_service import homologate_round
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.readiness import evaluate_round_readiness
from leagues.scoring_service import compute_round_results
from sports_data.fixtures.models import PlayerMatchStat


@dataclass(frozen=True)
class RoundCalculationResult:
    round_id: UUID
    league_id: UUID
    round_number: int
    fixtures_scored: int
    fallback: LineupFallbackResult | None
    result_final: bool
    homologated: bool


def calculate_league_round(
    session: Session,
    *,
    round_id: UUID,
    league_id: UUID,
    actor_id: UUID | None,
    automatic: bool,
) -> RoundCalculationResult:
    """Ricalcola un turno di una lega. Idempotente: rieseguirla non duplica nulla."""
    fantasy_round = session.execute(
        select(FantasyRound)
        .where(FantasyRound.id == round_id, FantasyRound.league_id == league_id)
        .with_for_update()
    ).scalar_one_or_none()
    if fantasy_round is None:
        raise ValidationAuthError("Turno non trovato.", code="turn_not_found")

    fixture_ids = list(
        session.scalars(
            select(FantasyRoundFixture.fixture_id).where(
                FantasyRoundFixture.round_id == round_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
    )
    fixtures_with_stats = set(
        session.scalars(
            select(PlayerMatchStat.fixture_id)
            .where(PlayerMatchStat.fixture_id.in_(fixture_ids))
            .distinct()
        ).all()
    )
    fixtures_scored = 0
    for fixture_id in fixture_ids:
        if fixture_id not in fixtures_with_stats:
            continue
        compute_fixture_ratings(session, fixture_id=fixture_id, league_id=league_id)
        fixtures_scored += 1

    fallback_result: LineupFallbackResult | None = None
    readiness = evaluate_round_readiness(session, round_id=round_id)
    if readiness.all_fixtures_finished:
        # Solo a turno concluso: prima di questo momento un fantallenatore ha
        # ancora tempo per schierare da sé (vedi fallback_service).
        fallback_result = ensure_lineup_submissions_for_round(
            session, round_id=round_id, league_id=league_id, actor_id=actor_id
        )

    compute_round_effective_lineups(session, round_id=round_id)
    scoring = compute_round_results(session, round_id=round_id)

    homologated = False
    if scoring.result_final and scoring.counters.skipped == 0:
        homologate_round(session, round_id=round_id, actor_id=actor_id, automatic=automatic)
        homologated = True

    return RoundCalculationResult(
        round_id=round_id,
        league_id=league_id,
        round_number=fantasy_round.number,
        fixtures_scored=fixtures_scored,
        fallback=fallback_result,
        result_final=scoring.result_final,
        homologated=homologated,
    )


__all__ = ["RoundCalculationResult", "calculate_league_round"]
