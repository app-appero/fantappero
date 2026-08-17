"""HTTP routes for round-level H2H results and standings (EP07-05 / EP07-06)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from authorization.dependencies import require_permissions
from database.enums import Permission
from fantasy_turns.models import FantasyRound
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.schemas import (
    ComputeRoundResultsRequest,
    ComputeRoundResultsResponse,
    ComputeStandingsResponse,
    RoundMatchResultResponse,
)
from leagues.scoring_service import compute_round_results
from leagues.standings_service import compute_league_standings

router = APIRouter(prefix="/fantasy-scoring", tags=["fantasy-scoring"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"message": exc.message, "code": exc.code})


@router.post(
    "/rounds/{round_id}/risultati",
    response_model=ComputeRoundResultsResponse,
)
def compute_round_results_endpoint(
    round_id: UUID,
    body: ComputeRoundResultsRequest,
    _operator: object = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> ComputeRoundResultsResponse | JSONResponse:
    """Somma i fantavoti effettivi, converte in gol fantasy e salva il risultato."""
    try:
        result = compute_round_results(
            session,
            round_id=round_id,
            formula_version=body.formula_version,
        )
    except AuthError as exc:
        return _error_response(exc)
    session.commit()
    return ComputeRoundResultsResponse(
        roundId=str(result.round_id),
        resultFinal=result.result_final,
        matchups=result.matchups,
        created=result.counters.created,
        updated=result.counters.updated,
        unchanged=result.counters.unchanged,
        skipped=result.counters.skipped,
    )


@router.get(
    "/rounds/{round_id}/risultati",
    response_model=list[RoundMatchResultResponse],
)
def list_round_results(
    round_id: UUID,
    _operator: object = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> list[RoundMatchResultResponse] | JSONResponse:
    """Risultati persistiti per un turno (una riga per scontro diretto, no bye)."""
    fantasy_round = session.get(FantasyRound, round_id)
    if fantasy_round is None:
        return JSONResponse(
            status_code=404,
            content={"message": "Turno non trovato.", "code": "turn_not_found"},
        )
    calendar = session.execute(
        select(LeagueCalendar).where(LeagueCalendar.league_id == fantasy_round.league_id)
    ).scalar_one_or_none()
    if calendar is None:
        return []
    slots = session.scalars(
        select(LeagueCalendarSlot)
        .where(
            LeagueCalendarSlot.calendar_id == calendar.id,
            LeagueCalendarSlot.round_number == fantasy_round.number,
            LeagueCalendarSlot.is_bye.is_(False),
        )
        .order_by(LeagueCalendarSlot.slot_index)
    ).all()
    return [
        RoundMatchResultResponse(
            slotIndex=slot.slot_index,
            homeMembershipId=str(slot.home_membership_id),
            awayMembershipId=str(slot.away_membership_id) if slot.away_membership_id else None,
            homeScore=slot.home_score,
            awayScore=slot.away_score,
            homeFantasyGoals=slot.home_fantasy_goals,
            awayFantasyGoals=slot.away_fantasy_goals,
            outcome=slot.outcome,
            resultFinal=slot.result_final,
            computedAt=slot.result_computed_at,
        )
        for slot in slots
    ]


@router.post(
    "/leagues/{league_id}/classifica",
    response_model=ComputeStandingsResponse,
)
def compute_standings_endpoint(
    league_id: UUID,
    _operator: object = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> ComputeStandingsResponse | JSONResponse:
    """Ricalcola la classifica dagli scontri diretti finali (mai incrementale)."""
    try:
        result = compute_league_standings(session, league_id=league_id)
    except AuthError as exc:
        return _error_response(exc)
    session.commit()
    return ComputeStandingsResponse(
        leagueId=str(result.league_id),
        teams=result.teams,
        matchesConsidered=result.matches_considered,
        created=result.counters.created,
        updated=result.counters.updated,
        unchanged=result.counters.unchanged,
        removed=result.counters.removed,
    )
