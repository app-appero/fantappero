"""HTTP routes for AI-assisted advice — advisory only, never auto-applied (EP10-02..05)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ai_assistant.analista_service import AnalistaService
from ai_assistant.exceptions import AiInteractionNotFoundError
from ai_assistant.feedback_service import record_feedback
from ai_assistant.osservatore_service import AthleteComparisonRow, OsservatoreService
from ai_assistant.quota_service import check_daily_quota
from ai_assistant.schemas import (
    AiFeedbackRequest,
    AiFeedbackResponse,
    AnalistaExplanationResponse,
    AthleteComparisonRowResponse,
    CompareAthletesRequest,
    LineupSuggestionResponse,
    OsservatoreResultResponse,
    ViceallenatoreAdviceResponse,
)
from ai_assistant.viceallenatore_service import ViceallenatoreService
from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from auth.models.user import User
from authorization.context import LeagueAccess
from authorization.dependencies import require_league_permissions, require_permissions
from billing.entitlement_service import EntitlementService
from database.enums import AiFeedbackRating, FantasyRole, Permission

router = APIRouter(prefix="/leagues", tags=["ai-assistant"])
feedback_router = APIRouter(prefix="/assistente", tags=["ai-assistant"])


def _error_response(exc: AuthError) -> JSONResponse:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code == "ai_quota_exceeded":
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    elif exc.code == "ai_interaction_not_found":
        status_code = status.HTTP_404_NOT_FOUND
    return JSONResponse(status_code=status_code, content={"message": exc.message, "code": exc.code})


def _check_quota(session: Session, user_id: UUID) -> None:
    limit = EntitlementService(session).get_status(user_id).ai_daily_limit
    check_daily_quota(session, user_id, limit=limit)


def _row_response(row: AthleteComparisonRow) -> AthleteComparisonRowResponse:
    return AthleteComparisonRowResponse(
        athleteId=str(row.athlete_id),
        name=row.name,
        role=row.role,
        avgRating=row.avg_rating,
        recentMinutesAvg=row.recent_minutes_avg,
        injured=row.injured,
        isFreeAgentInLeague=row.is_free_agent_in_league,
        nextOpponentName=row.next_opponent_name,
    )


@router.get(
    "/{league_id}/assistente/viceallenatore/{round_id}",
    response_model=ViceallenatoreAdviceResponse,
)
def get_viceallenatore_advice(
    round_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    session: Session = Depends(get_db_session),
) -> ViceallenatoreAdviceResponse | JSONResponse:
    try:
        _check_quota(session, league_access.user.id)
        advice = ViceallenatoreService(session).suggest(league_access, round_id)
    except AuthError as exc:
        return _error_response(exc)
    return ViceallenatoreAdviceResponse(
        suggestions=[
            LineupSuggestionResponse(
                starterAthleteId=str(s.starter_athlete_id),
                starterName=s.starter_name,
                benchAthleteId=str(s.bench_athlete_id),
                benchName=s.bench_name,
                reason=s.reason,
            )
            for s in advice.suggestions
        ],
        modificationAllowed=advice.modification_allowed,
        message=advice.message,
        interactionId=str(advice.interaction_id) if advice.interaction_id else None,
    )


@router.post(
    "/{league_id}/assistente/osservatore/confronto",
    response_model=OsservatoreResultResponse,
)
def compare_athletes(
    body: CompareAthletesRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    session: Session = Depends(get_db_session),
) -> OsservatoreResultResponse | JSONResponse:
    try:
        athlete_ids = [UUID(value) for value in body.athlete_ids]
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": "Identificativo giocatore non valido.",
                "code": "invalid_athlete_id",
            },
        )
    try:
        _check_quota(session, league_access.user.id)
        result = OsservatoreService(session).compare(league_access, athlete_ids)
    except AuthError as exc:
        return _error_response(exc)
    return OsservatoreResultResponse(
        rows=[_row_response(row) for row in result.rows],
        interactionId=str(result.interaction_id),
    )


@router.get(
    "/{league_id}/assistente/osservatore/obiettivi",
    response_model=OsservatoreResultResponse,
)
def suggest_free_agent_targets(
    role: FantasyRole = Query(...),
    season_year: int = Query(alias="seasonYear"),
    limit: int = Query(default=5, ge=1, le=20),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.MARKET_VIEW)),
    session: Session = Depends(get_db_session),
) -> OsservatoreResultResponse | JSONResponse:
    try:
        _check_quota(session, league_access.user.id)
        result = OsservatoreService(session).suggest_free_agent_targets(
            league_access, role=role, season_year=season_year, limit=limit
        )
    except AuthError as exc:
        return _error_response(exc)
    return OsservatoreResultResponse(
        rows=[_row_response(row) for row in result.rows],
        interactionId=str(result.interaction_id),
    )


@router.get(
    "/{league_id}/assistente/analista/{athlete_id}",
    response_model=AnalistaExplanationResponse,
)
def get_analista_explanation(
    athlete_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    session: Session = Depends(get_db_session),
) -> AnalistaExplanationResponse | JSONResponse:
    try:
        _check_quota(session, league_access.user.id)
        explanation = AnalistaService(session).explain(league_access, athlete_id)
    except AuthError as exc:
        return _error_response(exc)
    if explanation is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Giocatore non trovato.", "code": "athlete_not_found"},
        )
    return AnalistaExplanationResponse(
        athleteId=str(explanation.athlete_id),
        athleteName=explanation.athlete_name,
        asOf=explanation.as_of.isoformat(),
        explanation=explanation.explanation,
        limits=explanation.limits,
        sampleSize=explanation.sample_size,
        interactionId=str(explanation.interaction_id),
        cached=explanation.cached,
    )


@feedback_router.post(
    "/interazioni/{interaction_id}/feedback",
    response_model=AiFeedbackResponse,
)
def submit_ai_feedback(
    interaction_id: UUID,
    body: AiFeedbackRequest,
    current_user: User = Depends(require_permissions(Permission.PROFILE_VIEW)),
    session: Session = Depends(get_db_session),
) -> AiFeedbackResponse | JSONResponse:
    try:
        rating = AiFeedbackRating(body.rating)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Valutazione non valida.", "code": "invalid_feedback_rating"},
        )
    try:
        interaction = record_feedback(
            session, user_id=current_user.id, interaction_id=interaction_id, rating=rating
        )
    except AiInteractionNotFoundError as exc:
        return _error_response(exc)
    assert interaction.feedback_at is not None
    return AiFeedbackResponse(
        interactionId=str(interaction.id),
        rating=rating.value,
        feedbackAt=interaction.feedback_at.isoformat(),
    )
