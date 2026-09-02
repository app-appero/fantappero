"""Riparazione storico: turni con scontri H2H mai risolti (EP-turni-calcolo).

Trova turni le cui partite reali sono concluse ma che non si sono mai chiusi
correttamente — sia perché rimasti "provvisori" per sempre (il bug pre-fix:
nessuna omologazione automatica quando mancava una formazione), sia perché
sono stati omologati manualmente (`POST /fantasy-scoring/rounds/{id}/omologa`,
che verifica solo la disponibilità dei dati fixture/statistiche, non lo stato
degli scontri H2H) lasciando comunque scontri irrisolti. Tocca solo i turni
con un buco reale: nessuna modifica a un turno già correttamente completato.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.enums import FantasyRoundHomologationStatus, FantasyTurnStatus, LeagueState
from fantasy_turns.homologation_service import apply_round_correction
from fantasy_turns.models import FantasyRound
from fantasy_turns.readiness import evaluate_round_readiness
from fantasy_turns.round_calculation_service import RoundCalculationResult, calculate_league_round
from leagues.calendar_round_mapping import h2h_round_numbers_for_round
from leagues.models.league import League
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot


@dataclass(frozen=True)
class RoundRepairCandidate:
    round_id: UUID
    league_id: UUID
    round_number: int
    was_homologated: bool


@dataclass
class HistoricalRepairResult:
    leagues: int = 0
    rounds_considered: int = 0
    rounds_repaired: int = 0
    rounds_failed: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "leagues": self.leagues,
            "roundsConsidered": self.rounds_considered,
            "roundsRepaired": self.rounds_repaired,
            "roundsFailed": self.rounds_failed,
            "errors": list(self.errors),
        }


def find_rounds_needing_repair(
    session: Session, *, league_id: UUID | None = None
) -> list[RoundRepairCandidate]:
    """Turni le cui partite sono concluse ma con almeno uno scontro H2H mai risolto."""
    round_query = select(FantasyRound).where(FantasyRound.status != FantasyTurnStatus.SKIPPED)
    if league_id is not None:
        round_query = round_query.where(FantasyRound.league_id == league_id)
    else:
        round_query = round_query.join(League, League.id == FantasyRound.league_id).where(
            League.state == LeagueState.ACTIVE
        )

    candidates: list[RoundRepairCandidate] = []
    rounds = session.scalars(
        round_query.order_by(FantasyRound.league_id.asc(), FantasyRound.number.asc())
    ).all()
    for fantasy_round in rounds:
        readiness = evaluate_round_readiness(session, round_id=fantasy_round.id)
        if not readiness.all_fixtures_finished:
            continue
        if _round_is_fully_resolved(session, fantasy_round):
            continue
        candidates.append(
            RoundRepairCandidate(
                round_id=fantasy_round.id,
                league_id=fantasy_round.league_id,
                round_number=fantasy_round.number,
                was_homologated=(
                    fantasy_round.homologation_status
                    == FantasyRoundHomologationStatus.HOMOLOGATED
                ),
            )
        )
    return candidates


def _round_is_fully_resolved(session: Session, fantasy_round: FantasyRound) -> bool:
    calendar = session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == fantasy_round.league_id)
    ).first()
    if calendar is None:
        # Nessun calendario H2H per questa lega: niente da riparare qui.
        return True

    round_numbers = h2h_round_numbers_for_round(session, calendar=calendar, fantasy_round=fantasy_round)
    if not round_numbers:
        return True

    unresolved = session.execute(
        select(LeagueCalendarSlot.id)
        .where(
            LeagueCalendarSlot.calendar_id == calendar.id,
            LeagueCalendarSlot.round_number.in_(round_numbers),
            LeagueCalendarSlot.is_bye.is_(False),
            LeagueCalendarSlot.result_final.is_not(True),
        )
        .limit(1)
    ).first()
    return unresolved is None


def repair_round(
    session: Session,
    *,
    round_id: UUID,
    league_id: UUID,
    actor_id: UUID | None,
    reason: str,
) -> RoundCalculationResult:
    """Riapre (se serve) e ricalcola un turno con lo stesso motore di sempre."""
    fantasy_round = session.get(FantasyRound, round_id)
    if (
        fantasy_round is not None
        and fantasy_round.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED
    ):
        apply_round_correction(session, round_id=round_id, actor_id=actor_id, reason=reason)
    return calculate_league_round(
        session, round_id=round_id, league_id=league_id, actor_id=actor_id, automatic=False
    )


def repair_historical_rounds_for_active_leagues(
    session: Session, *, actor_id: UUID | None, reason: str
) -> HistoricalRepairResult:
    """Ripara tutti i turni con un buco storico, isolando un fallimento per turno."""
    result = HistoricalRepairResult()
    result.leagues = len(
        list(session.scalars(select(League.id).where(League.state == LeagueState.ACTIVE)).all())
    )

    candidates = find_rounds_needing_repair(session)
    result.rounds_considered = len(candidates)
    for candidate in candidates:
        try:
            with session.begin_nested():
                repair_round(
                    session,
                    round_id=candidate.round_id,
                    league_id=candidate.league_id,
                    actor_id=actor_id,
                    reason=reason,
                )
            result.rounds_repaired += 1
        except Exception as exc:  # noqa: BLE001 - isolate a single round's failure
            result.rounds_failed += 1
            result.errors.append({"roundId": str(candidate.round_id), "code": type(exc).__name__})
    return result


__all__ = [
    "HistoricalRepairResult",
    "RoundRepairCandidate",
    "find_rounds_needing_repair",
    "repair_historical_rounds_for_active_leagues",
    "repair_round",
]
