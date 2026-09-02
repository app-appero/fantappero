"""Fantasy team HTTP routes (EP05-01/02/03/04/06)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session
from auth.exceptions import AuthError
from authorization.context import LeagueAccess
from authorization.dependencies import require_league_permissions
from database.enums import Permission
from fantasy_teams.schemas import (
    AdminCreditMovementRequest,
    AssignRosterSlotRequest,
    CreateRosterTurnSnapshotRequest,
    CreditAccountResponse,
    CreditLedgerListResponse,
    EnsureFantasyTeamsResponse,
    FantasyTeamResponse,
    FantasyTeamSummaryResponse,
    RosterAsOfResponse,
    RosterImportConfirmRequest,
    RosterImportConfirmResponse,
    RosterImportPreviewResponse,
    RosterImportTextPreviewRequest,
    RosterOccupancyEntryResponse,
    RosterOwnershipHistoryResponse,
    RosterTurnSnapshotDetailResponse,
    RosterTurnSnapshotSummaryResponse,
    TeamRosterPlayerResponse,
)
from fantasy_teams.service import FantasyTeamService

router = APIRouter(prefix="/leagues", tags=["fantasy-teams"])


def _error_response(exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"message": exc.message, "code": exc.code},
    )


def get_fantasy_team_service(
    session: Session = Depends(get_db_session),
) -> FantasyTeamService:
    return FantasyTeamService(session)


@router.get("/{league_id}/rosa", response_model=FantasyTeamResponse)
def get_my_fantasy_roster(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> FantasyTeamResponse | JSONResponse:
    """Return the caller's fantasy team (created lazily if missing)."""
    try:
        return service.get_my_team(league_access)
    except AuthError as exc:
        return _error_response(exc)


@router.get("/{league_id}/squadre", response_model=list[FantasyTeamSummaryResponse])
def list_fantasy_teams(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> list[FantasyTeamSummaryResponse]:
    """List fantasy teams in the league."""
    return service.list_teams(league_access)


@router.get(
    "/{league_id}/occupazione-rosa",
    response_model=list[RosterOccupancyEntryResponse],
)
def list_roster_occupancy(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> list[RosterOccupancyEntryResponse]:
    """Return league-wide athlete occupancy for manual roster editing."""
    return service.list_roster_occupancy(league_access)


@router.get(
    "/{league_id}/squadre/{team_id}/giocatori",
    response_model=list[TeamRosterPlayerResponse],
)
def list_team_players_for_trade(
    team_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> list[TeamRosterPlayerResponse] | JSONResponse:
    """Rosa corrente di una squadra della lega, per proposte di scambio (EP08-05)."""
    try:
        return service.list_team_players_for_trade(league_access, team_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/rosa/storico",
    response_model=RosterOwnershipHistoryResponse,
)
def get_my_roster_history(
    active_only: bool = Query(default=False, alias="activeOnly"),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> RosterOwnershipHistoryResponse | JSONResponse:
    """Return ownership intervals for the caller's fantasy team (EP05-06)."""
    try:
        return service.list_my_ownership_history(league_access, active_only=active_only)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/amministrazione/squadre/{team_id}/rosa/storico",
    response_model=RosterOwnershipHistoryResponse,
)
def get_team_roster_history_for_admin(
    team_id: UUID,
    active_only: bool = Query(default=False, alias="activeOnly"),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> RosterOwnershipHistoryResponse | JSONResponse:
    """Return ownership intervals for a participant team (admin)."""
    try:
        return service.list_team_ownership_history(league_access, team_id, active_only=active_only)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/rosa/as-of",
    response_model=RosterAsOfResponse,
)
def get_my_roster_as_of(
    at: str | None = Query(default=None),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> RosterAsOfResponse | JSONResponse:
    """Reconstruct the caller's roster at an ISO-8601 UTC timestamp (EP05-06)."""
    try:
        return service.get_my_roster_as_of(league_access, at=at)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/rosa/snapshot-turni",
    response_model=list[RosterTurnSnapshotSummaryResponse],
)
def list_roster_turn_snapshots(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> list[RosterTurnSnapshotSummaryResponse]:
    """List immutable roster snapshots keyed by round number."""
    return service.list_turn_snapshots(league_access)


@router.get(
    "/{league_id}/rosa/snapshot-turni/{round_number}",
    response_model=RosterTurnSnapshotDetailResponse,
)
def get_roster_turn_snapshot(
    round_number: int,
    team_id: UUID | None = Query(default=None, alias="teamId"),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> RosterTurnSnapshotDetailResponse | JSONResponse:
    """Return a roster turn snapshot detail (optionally filtered by team)."""
    try:
        return service.get_turn_snapshot(league_access, round_number, team_id=team_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/amministrazione/rosa/snapshot-turni",
    response_model=RosterTurnSnapshotDetailResponse,
)
def create_roster_turn_snapshot(
    body: CreateRosterTurnSnapshotRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> RosterTurnSnapshotDetailResponse | JSONResponse:
    """Create an immutable league roster snapshot for a round (idempotent)."""
    try:
        return service.create_turn_snapshot_for_league(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/amministrazione/squadre/{team_id}",
    response_model=FantasyTeamResponse,
)
def get_fantasy_team_for_admin(
    team_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> FantasyTeamResponse | JSONResponse:
    """Return a participant roster for admin manual assignment (EP05-03)."""
    try:
        return service.get_team_for_admin(league_access, team_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/amministrazione/squadre/{team_id}/crediti",
    response_model=CreditLedgerListResponse,
)
def get_team_credits_for_admin(
    team_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> CreditLedgerListResponse | JSONResponse:
    """Return credit balance and ledger for a participant team (admin)."""
    try:
        return service.get_team_credits_for_admin(league_access, team_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get("/{league_id}/crediti", response_model=CreditAccountResponse)
def get_my_credits(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> CreditAccountResponse | JSONResponse:
    """Return the caller's credit balance (reconstructable from ledger)."""
    try:
        return service.get_my_credits(league_access)
    except AuthError as exc:
        return _error_response(exc)


@router.get("/{league_id}/crediti/movimenti", response_model=CreditLedgerListResponse)
def list_my_credit_movements(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_VIEW)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> CreditLedgerListResponse | JSONResponse:
    """Return the caller's immutable credit ledger entries."""
    try:
        return service.list_my_credit_movements(league_access)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/amministrazione/crediti/movimenti",
    response_model=CreditLedgerListResponse,
)
def admin_post_credit_movement(
    body: AdminCreditMovementRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> CreditLedgerListResponse | JSONResponse:
    """Post an admin credit adjustment via append-only ledger (idempotent)."""
    try:
        return service.admin_post_credit_movement(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/amministrazione/squadre",
    response_model=EnsureFantasyTeamsResponse,
)
def ensure_fantasy_teams(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> EnsureFantasyTeamsResponse | JSONResponse:
    """Ensure every participant has a fantasy team with empty roster slots."""
    try:
        return service.ensure_all_teams(league_access)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/amministrazione/squadre/{team_id}/rosa/random",
    response_model=FantasyTeamResponse,
)
def assign_random_ai_roster(
    team_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> FantasyTeamResponse | JSONResponse:
    """Fill an AI manager's empty roster slots with random free listone athletes."""
    try:
        return service.assign_random_ai_roster(league_access, team_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get("/{league_id}/amministrazione/import-csv/modello")
def download_roster_csv_template(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> Response:
    """Download the official CSV template for roster import (EP05-04)."""
    _ = league_access
    content = service.download_csv_template()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="fantappero-import-rosa.csv"',
        },
    )


@router.post(
    "/{league_id}/amministrazione/import-csv/anteprima",
    response_model=RosterImportPreviewResponse,
)
async def preview_roster_csv_import(
    file: UploadFile = File(...),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> RosterImportPreviewResponse | JSONResponse:
    """Parse and validate a CSV without writing roster/credits (EP05-04)."""
    try:
        data = await file.read()
        return service.preview_csv_import(
            league_access,
            data=data,
            filename=file.filename,
        )
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/amministrazione/import-csv/anteprima-testo",
    response_model=RosterImportPreviewResponse,
)
def preview_roster_csv_import_text(
    body: RosterImportTextPreviewRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> RosterImportPreviewResponse | JSONResponse:
    """Parse pasted CSV text without writing roster/credits (mobile-friendly)."""
    try:
        return service.preview_csv_import(
            league_access,
            data=body.csv_text.encode("utf-8"),
            filename="incolla.csv",
        )
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/amministrazione/import-csv/{import_id}/conferma",
    response_model=RosterImportConfirmResponse,
)
def confirm_roster_csv_import(
    import_id: UUID,
    body: RosterImportConfirmRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> RosterImportConfirmResponse | JSONResponse:
    """Atomically apply a previously previewed CSV import (EP05-04)."""
    try:
        return service.confirm_csv_import(league_access, import_id, body)
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
    response_model=FantasyTeamResponse,
)
def assign_fantasy_roster_slot(
    team_id: UUID,
    slot_index: int,
    body: AssignRosterSlotRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_EDIT)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> FantasyTeamResponse | JSONResponse:
    """Assign an athlete to a roster slot (own team, or any team if admin)."""
    try:
        return service.assign_slot(league_access, team_id, slot_index, body)
    except AuthError as exc:
        return _error_response(exc)


@router.delete(
    "/{league_id}/amministrazione/squadre/{team_id}/slot/{slot_index}",
    response_model=FantasyTeamResponse,
)
def release_fantasy_roster_slot(
    team_id: UUID,
    slot_index: int,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.ROSTER_EDIT)),
    service: FantasyTeamService = Depends(get_fantasy_team_service),
) -> FantasyTeamResponse | JSONResponse:
    """Release an athlete from a roster slot (own team, or any team if admin)."""
    try:
        return service.release_slot(league_access, team_id, slot_index)
    except AuthError as exc:
        return _error_response(exc)
