"""HTTP routes for fantasy lineups (EP06-02 / EP06-03 / EP06-04 / EP06-05 / EP06-06)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from authorization.context import LeagueAccess
from authorization.dependencies import require_league_permissions, require_permissions
from database.enums import LeagueAuditAction, Permission
from fantasy_lineups.ai_service import (
    AI_LINEUP_ALGORITHM_VERSION,
    run_ai_lineups_for_round,
)
from fantasy_lineups.schemas import (
    AiLineupRunResponse,
    AiLineupTeamResultResponse,
    ComputeEffectiveLineupsRequest,
    ComputeEffectiveLineupsResponse,
    EffectiveLineupResponse,
    LineupContextResponse,
    SaveLineupDraftRequest,
    SaveLineupRequest,
    SkippedBenchCandidateResponse,
    SubstitutionResponse,
)
from fantasy_lineups.service import FantasyLineupService
from fantasy_lineups.substitution_service import (
    compute_round_effective_lineups,
    get_effective_lineup,
)
from leagues.models.league_audit_event import LeagueAuditEvent
from observability.context import get_correlation_id

router = APIRouter(prefix="/leagues", tags=["fantasy-lineups"])
effective_lineup_router = APIRouter(prefix="/fantasy-lineups", tags=["fantasy-lineups"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": exc.message, "code": exc.code},
    )


def get_fantasy_lineup_service(
    session: Session = Depends(get_db_session),
) -> FantasyLineupService:
    return FantasyLineupService(session)


@router.get(
    "/{league_id}/turni/{round_id}/formazione",
    response_model=LineupContextResponse,
)
def get_my_lineup(
    round_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyLineupService = Depends(get_fantasy_lineup_service),
) -> LineupContextResponse | JSONResponse:
    """Formazione del chiamante per il turno (moduli, rosa, lock per kickoff)."""
    try:
        return service.get_my_lineup(league_access, round_id)
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/turni/{round_id}/formazione",
    response_model=LineupContextResponse,
)
def save_my_lineup(
    round_id: UUID,
    body: SaveLineupRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_EDIT)),
    service: FantasyLineupService = Depends(get_fantasy_lineup_service),
) -> LineupContextResponse | JSONResponse:
    """Salva la formazione se modulo, panchina e lock per-calciatore sono validi."""
    try:
        return service.save_my_lineup(league_access, round_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/turni/{round_id}/formazione/copia",
    response_model=LineupContextResponse,
)
def copy_previous_lineup_to_draft(
    round_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_EDIT)),
    service: FantasyLineupService = Depends(get_fantasy_lineup_service),
) -> LineupContextResponse | JSONResponse:
    """Copia la formazione precedente in bozza, rivalidata su rosa e lock correnti."""
    try:
        return service.copy_previous_to_draft(league_access, round_id)
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/turni/{round_id}/formazione/bozza",
    response_model=LineupContextResponse,
)
def save_my_lineup_draft(
    round_id: UUID,
    body: SaveLineupDraftRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_EDIT)),
    service: FantasyLineupService = Depends(get_fantasy_lineup_service),
) -> LineupContextResponse | JSONResponse:
    """Salva una bozza incompleta senza confermare né consumare mosse tattiche."""
    try:
        return service.save_my_draft(league_access, round_id, body)
    except AuthError as exc:
        return _error_response(exc)


def _to_effective_lineup_response(row: object) -> EffectiveLineupResponse:
    return EffectiveLineupResponse(
        id=str(row.id),
        roundId=str(row.round_id),
        fantasyTeamId=str(row.fantasy_team_id),
        submissionId=str(row.submission_id),
        module=row.module.value,
        moduleValid=row.module_valid,
        maxAutomaticSubstitutions=row.max_automatic_substitutions,
        effectiveStarterIds=list(row.effective_starter_ids),
        substitutions=[
            SubstitutionResponse(
                outAthleteId=item["outAthleteId"],
                inAthleteId=item["inAthleteId"],
                role=item["role"],
                order=item["order"],
            )
            for item in row.substitutions_json
        ],
        skipped=[
            SkippedBenchCandidateResponse(
                athleteId=item["athleteId"],
                role=item["role"],
                reason=item["reason"],
            )
            for item in row.skipped_json
        ],
        computedAt=row.computed_at,
    )


@effective_lineup_router.post(
    "/rounds/{round_id}/formazione-effettiva",
    response_model=ComputeEffectiveLineupsResponse,
)
def compute_effective_lineups(
    round_id: UUID,
    body: ComputeEffectiveLineupsRequest,
    _operator: object = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> ComputeEffectiveLineupsResponse | JSONResponse:
    """Risolve e persiste le sostituzioni automatiche per tutte le squadre del turno."""
    try:
        result = compute_round_effective_lineups(
            session,
            round_id=round_id,
            max_automatic_substitutions=body.max_automatic_substitutions,
        )
    except AuthError as exc:
        return _error_response(exc)
    session.commit()
    return ComputeEffectiveLineupsResponse(
        roundId=str(result.round_id),
        maxAutomaticSubstitutions=result.max_automatic_substitutions,
        teams=result.teams,
        created=result.counters.created,
        updated=result.counters.updated,
        unchanged=result.counters.unchanged,
    )


@effective_lineup_router.get(
    "/rounds/{round_id}/formazione-effettiva/{fantasy_team_id}",
    response_model=EffectiveLineupResponse,
)
def get_round_effective_lineup(
    round_id: UUID,
    fantasy_team_id: UUID,
    _operator: object = Depends(require_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> EffectiveLineupResponse | JSONResponse:
    """Formazione effettiva persistita per una squadra fantasy nel turno."""
    row = get_effective_lineup(session, round_id=round_id, fantasy_team_id=fantasy_team_id)
    if row is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"message": "Formazione effettiva non trovata.", "code": "not_found"},
        )
    return _to_effective_lineup_response(row)


@router.post(
    "/{league_id}/turni/{round_id}/formazioni-ia",
    response_model=AiLineupRunResponse,
)
def run_ai_lineups(
    round_id: UUID,
    dry_run: bool = False,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.GLOBAL_OPERATE)),
    session: Session = Depends(get_db_session),
) -> AiLineupRunResponse | JSONResponse:
    """Preview o ricalcolo delle formazioni automatiche IA (EP13-P05).

    Idempotente: non tocca le squadre umane né le formazioni già schierate
    a mano. Con ``dry_run=true`` non persiste nulla.

    Solo operatore di piattaforma (EP-turni-automazione): la generazione gira
    già in automatico da cron per tutti i turni aperti, questo endpoint resta
    l'override manuale puntuale.
    """
    try:
        results = run_ai_lineups_for_round(
            session,
            league_id=league_access.league.id,
            round_id=round_id,
            dry_run=dry_run,
        )
    except AuthError as exc:
        return _error_response(exc)

    teams = [
        AiLineupTeamResultResponse(
            fantasyTeamId=str(item.fantasy_team_id),
            fantasyTeamName=item.fantasy_team_name,
            outcome=item.outcome,
            message=item.message,
            starters=0 if item.plan is None else len(item.plan.starters),
            usedFallback=False if item.plan is None else item.plan.used_fallback,
        )
        for item in results
    ]
    counts = {
        outcome: sum(1 for item in results if item.outcome == outcome)
        for outcome in {
            "created",
            "updated",
            "unchanged",
            "skipped_locked",
            "skipped_manual",
            "incomplete",
        }
    }
    handled = len(teams) - counts["incomplete"]
    if dry_run:
        summary = f"Anteprima: {len(teams)} squadre AI valutate"
    else:
        summary = (
            f"Formazioni AI gestite: {handled}/{len(teams)} "
            f"({counts['created']} create, {counts['updated']} aggiornate, "
            f"{counts['unchanged']} già valide, "
            f"{counts['skipped_locked']} bloccate, {counts['incomplete']} non generate)"
        )
        session.add(
            LeagueAuditEvent(
                league_id=league_access.league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.FANTASY_LINEUP_SAVED,
                correlation_id=get_correlation_id(),
                details={
                    "source": "admin_ai_lineup_command",
                    "roundId": str(round_id),
                    "algorithmVersion": AI_LINEUP_ALGORITHM_VERSION,
                    "teamsEvaluated": len(teams),
                    "teamsHandled": handled,
                    "counts": counts,
                    "errors": [
                        {
                            "fantasyTeamId": item.fantasy_team_id,
                            "fantasyTeamName": item.fantasy_team_name,
                            "message": item.message,
                        }
                        for item in teams
                        if item.outcome == "incomplete"
                    ],
                },
            )
        )
        session.commit()
    return AiLineupRunResponse(
        roundId=str(round_id),
        algorithmVersion=AI_LINEUP_ALGORITHM_VERSION,
        dryRun=dry_run,
        teams=teams,
        summary=summary,
    )
