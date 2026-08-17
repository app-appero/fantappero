"""League HTTP routes with authorization policies (EP02-03 / EP03-01)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth.dependencies import get_db_session, get_rate_limiter
from auth.exceptions import AuthError
from auth.models.user import User
from auth.rate_limit import AuthRateLimiter
from authorization.context import LeagueAccess
from authorization.dependencies import (
    get_authorization_service,
    require_league_permissions,
    require_permissions,
)
from authorization.service import AuthorizationService
from config.settings.api import ApiSettings
from config.settings.loader import get_api_settings
from database.enums import Permission, UserType
from leagues.calendar_service import LeagueCalendarService
from leagues.invite_service import LeagueInviteService
from leagues.listone_service import LeagueListoneService
from leagues.membership_service import LeagueMembershipService
from leagues.named_invite_service import NamedLeagueInviteService
from leagues.schemas import (
    AcceptLeagueInviteRequest,
    AcceptLeagueInviteResponse,
    CompetitionSummaryResponse,
    CreateLeagueInviteRequest,
    CreateLeagueInviteResponse,
    CreateLeagueRequest,
    CreateNamedLeagueInviteRequest,
    FantasyCoachDirectoryResponse,
    LeagueAdminPanelResponse,
    LeagueCalendarResponse,
    LeagueDetailResponse,
    LeagueInviteResponse,
    LeagueLifecycleResponse,
    LeagueListoneEntryResponse,
    LeagueListoneRefreshJobResponse,
    LeagueListoneRefreshProgressResponse,
    LeagueListoneRefreshResponse,
    LeagueMemberResponse,
    LeagueRulesResponse,
    LeagueStandingResponse,
    LeagueSummaryResponse,
    NamedLeagueInviteResponse,
    RespondNamedLeagueInviteResponse,
    SetLeagueRoleOverrideRequest,
    TransitionLeagueStateRequest,
    UpdateLeagueRulesRequest,
)
from leagues.service import LeagueService
from leagues.standings_service import list_league_standings

router = APIRouter(prefix="/leagues", tags=["leagues"])


def _error_response(exc: AuthError) -> JSONResponse:
    status_code = (
        status.HTTP_429_TOO_MANY_REQUESTS
        if exc.code == "rate_limit_exceeded"
        else status.HTTP_400_BAD_REQUEST
    )
    return JSONResponse(
        status_code=status_code,
        content={"message": exc.message, "code": exc.code},
    )


def get_league_service(
    session: Session = Depends(get_db_session),
    authz: AuthorizationService = Depends(get_authorization_service),
) -> LeagueService:
    return LeagueService(session, authz)


def get_league_invite_service(
    session: Session = Depends(get_db_session),
    settings: ApiSettings = Depends(get_api_settings),
) -> LeagueInviteService:
    return LeagueInviteService(session, settings)


def get_league_membership_service(
    session: Session = Depends(get_db_session),
) -> LeagueMembershipService:
    return LeagueMembershipService(session)


def get_named_league_invite_service(
    session: Session = Depends(get_db_session),
    rate_limiter: AuthRateLimiter | None = Depends(get_rate_limiter),
) -> NamedLeagueInviteService:
    return NamedLeagueInviteService(session, rate_limiter)


def get_league_calendar_service(
    session: Session = Depends(get_db_session),
) -> LeagueCalendarService:
    return LeagueCalendarService(session)


def get_league_listone_service(
    session: Session = Depends(get_db_session),
) -> LeagueListoneService:
    return LeagueListoneService(session)


@router.get("/competitions", response_model=list[CompetitionSummaryResponse])
def list_competitions(
    _current_user: User = Depends(require_permissions(Permission.LEAGUE_VIEW)),
    service: LeagueService = Depends(get_league_service),
) -> list[CompetitionSummaryResponse]:
    """List MVP competitions available when configuring a league."""
    return service.list_competitions()


@router.post("", response_model=LeagueDetailResponse, status_code=status.HTTP_201_CREATED)
def create_league(
    body: CreateLeagueRequest,
    current_user: User = Depends(require_permissions(Permission.LEAGUE_VIEW)),
    service: LeagueService = Depends(get_league_service),
) -> LeagueDetailResponse | JSONResponse:
    """Create a private league in draft state; caller becomes league admin."""
    try:
        return service.create_league(current_user, body)
    except AuthError as exc:
        return _error_response(exc)


@router.get("/mine", response_model=list[LeagueSummaryResponse])
def list_my_leagues(
    current_user: User = Depends(require_permissions(Permission.LEAGUE_VIEW)),
    service: LeagueService = Depends(get_league_service),
) -> list[LeagueSummaryResponse]:
    """List leagues the caller belongs to (tenant membership, no cross-league data)."""
    return service.list_user_leagues(current_user.id)


@router.post("/inviti/accetta", response_model=AcceptLeagueInviteResponse)
def accept_league_invite(
    body: AcceptLeagueInviteRequest,
    current_user: User = Depends(require_permissions(Permission.LEAGUE_VIEW)),
    service: LeagueInviteService = Depends(get_league_invite_service),
) -> AcceptLeagueInviteResponse | JSONResponse:
    """Join a draft league using a valid invite token or code."""
    try:
        return service.accept(current_user, body)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/inviti-ricevuti",
    response_model=list[NamedLeagueInviteResponse],
)
def list_received_named_invites(
    current_user: User = Depends(require_permissions(Permission.LEAGUE_VIEW)),
    service: NamedLeagueInviteService = Depends(get_named_league_invite_service),
) -> list[NamedLeagueInviteResponse]:
    return service.received(current_user)


@router.post(
    "/inviti-ricevuti/{invite_id}/accetta",
    response_model=RespondNamedLeagueInviteResponse,
)
def accept_named_invite(
    invite_id: UUID,
    current_user: User = Depends(require_permissions(Permission.LEAGUE_VIEW)),
    service: NamedLeagueInviteService = Depends(get_named_league_invite_service),
) -> RespondNamedLeagueInviteResponse | JSONResponse:
    try:
        return service.accept(current_user, invite_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/inviti-ricevuti/{invite_id}/rifiuta",
    response_model=RespondNamedLeagueInviteResponse,
)
def decline_named_invite(
    invite_id: UUID,
    current_user: User = Depends(require_permissions(Permission.LEAGUE_VIEW)),
    service: NamedLeagueInviteService = Depends(get_named_league_invite_service),
) -> RespondNamedLeagueInviteResponse | JSONResponse:
    try:
        return service.decline(current_user, invite_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get("/{league_id}", response_model=LeagueDetailResponse)
def get_league(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_VIEW)),
    service: LeagueService = Depends(get_league_service),
) -> LeagueDetailResponse:
    return service.get_league_detail(league_access)


@router.delete(
    "/{league_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_league(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueService = Depends(get_league_service),
) -> Response:
    """Hard-delete a league still in draft/configuring; archive otherwise."""
    try:
        service.delete_league(league_access)
    except AuthError as exc:
        return _error_response(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{league_id}/partecipanti",
    response_model=list[LeagueMemberResponse],
)
def list_league_members_public(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_VIEW)),
    service: LeagueMembershipService = Depends(get_league_membership_service),
) -> list[LeagueMemberResponse]:
    """Read-only participant roster for any league member (EP03-UX-02)."""
    return service.list(league_access)


@router.get(
    "/{league_id}/amministrazione/fantallenatori",
    response_model=FantasyCoachDirectoryResponse,
)
def list_fantasy_coaches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50, alias="pageSize"),
    search: str | None = Query(default=None, max_length=80),
    user_type: UserType | None = Query(default=None, alias="userType"),
    available: bool | None = Query(default=None),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: NamedLeagueInviteService = Depends(get_named_league_invite_service),
) -> FantasyCoachDirectoryResponse:
    return service.directory(
        league_access,
        page=page,
        page_size=page_size,
        search=search,
        user_type=user_type,
        available=available,
    )


@router.post(
    "/{league_id}/amministrazione/inviti-nominativi",
    response_model=NamedLeagueInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_named_invite(
    body: CreateNamedLeagueInviteRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: NamedLeagueInviteService = Depends(get_named_league_invite_service),
) -> NamedLeagueInviteResponse | JSONResponse:
    try:
        return service.create(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.delete(
    "/{league_id}/amministrazione/inviti-nominativi/{invite_id}",
    response_model=NamedLeagueInviteResponse,
)
def revoke_named_invite(
    invite_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: NamedLeagueInviteService = Depends(get_named_league_invite_service),
) -> NamedLeagueInviteResponse | JSONResponse:
    try:
        return service.revoke(league_access, invite_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get("/{league_id}/amministrazione", response_model=LeagueAdminPanelResponse)
def get_league_admin_panel(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueService = Depends(get_league_service),
) -> LeagueAdminPanelResponse:
    return service.get_admin_panel(league_access)


@router.post(
    "/{league_id}/amministrazione/stato",
    response_model=LeagueLifecycleResponse,
)
def transition_league_state(
    body: TransitionLeagueStateRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueService = Depends(get_league_service),
) -> LeagueLifecycleResponse | JSONResponse:
    """Validate and apply an atomic league lifecycle transition."""
    try:
        return service.transition_state(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.put("/{league_id}/amministrazione/regolamento", response_model=LeagueRulesResponse)
def update_league_rules(
    body: UpdateLeagueRulesRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueService = Depends(get_league_service),
) -> LeagueRulesResponse | JSONResponse:
    """Update league rules while the league is configurable."""
    try:
        return service.update_rules(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/amministrazione/calendario",
    response_model=LeagueCalendarResponse | None,
)
def get_admin_league_calendar(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueCalendarService = Depends(get_league_calendar_service),
) -> LeagueCalendarResponse | None:
    """Return the current draft or confirmed H2H calendar for league administration."""
    return service.get_admin_calendar(league_access)


@router.post(
    "/{league_id}/amministrazione/calendario/genera",
    response_model=LeagueCalendarResponse,
)
def generate_league_calendar(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueCalendarService = Depends(get_league_calendar_service),
) -> LeagueCalendarResponse | JSONResponse:
    """Generate a balanced single round-robin preview (FR-LEG-04)."""
    try:
        return service.generate(league_access)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/amministrazione/calendario/conferma",
    response_model=LeagueCalendarResponse,
)
def confirm_league_calendar(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueCalendarService = Depends(get_league_calendar_service),
) -> LeagueCalendarResponse | JSONResponse:
    """Confirm the generated calendar; idempotent when already confirmed."""
    try:
        return service.confirm(league_access)
    except AuthError as exc:
        return _error_response(exc)


@router.get("/{league_id}/calendario", response_model=LeagueCalendarResponse | None)
def get_league_calendar(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_VIEW)),
    service: LeagueCalendarService = Depends(get_league_calendar_service),
) -> LeagueCalendarResponse | None:
    """Return the confirmed calendar for all league members."""
    return service.get_public_calendar(league_access)


@router.get(
    "/{league_id}/listone",
    response_model=list[LeagueListoneEntryResponse],
)
def list_league_listone(
    current_round: int = Query(default=0, ge=0, alias="currentRound"),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_VIEW)),
    service: LeagueListoneService = Depends(get_league_listone_service),
) -> list[LeagueListoneEntryResponse]:
    """Listone ufficiale della stagione con eventuali override di lega."""
    return service.list_entries(league_access, current_round=current_round)


@router.post(
    "/{league_id}/amministrazione/listone/aggiorna",
    response_model=LeagueListoneRefreshJobResponse,
)
def refresh_league_listone(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueListoneService = Depends(get_league_listone_service),
) -> LeagueListoneRefreshJobResponse | JSONResponse:
    """Avvia sync async catalogo+rose MVP e generazione listone (poll progresso)."""
    try:
        return service.start_refresh_job(league_access)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/amministrazione/listone/aggiorna/{job_id}",
    response_model=LeagueListoneRefreshProgressResponse,
)
def get_league_listone_refresh_progress(
    job_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueListoneService = Depends(get_league_listone_service),
) -> LeagueListoneRefreshProgressResponse | JSONResponse:
    """Stato percentuale di un job di aggiornamento listone."""
    try:
        return service.get_refresh_progress(league_access, str(job_id))
    except AuthError as exc:
        return _error_response(exc)


@router.put(
    "/{league_id}/amministrazione/listone/{athlete_id}/ruolo",
    response_model=LeagueListoneEntryResponse,
)
def set_league_role_override(
    athlete_id: UUID,
    body: SetLeagueRoleOverrideRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueListoneService = Depends(get_league_listone_service),
) -> LeagueListoneEntryResponse | JSONResponse:
    """Imposta override ruolo pre-asta (immediato) o post-avvio (turno successivo)."""
    try:
        return service.set_override(
            league_access,
            athlete_id=athlete_id,
            role=body.role,
            current_round=body.current_round,
            reason=body.reason,
        )
    except AuthError as exc:
        return _error_response(exc)


@router.delete(
    "/{league_id}/amministrazione/listone/{athlete_id}/ruolo",
    response_model=LeagueListoneEntryResponse,
)
def clear_league_role_override(
    athlete_id: UUID,
    current_round: int = Query(default=0, ge=0, alias="currentRound"),
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueListoneService = Depends(get_league_listone_service),
) -> LeagueListoneEntryResponse | JSONResponse:
    """Rimuove l'override attivo e ripristina il ruolo ufficiale."""
    try:
        return service.clear_role_override(
            league_access,
            athlete_id=athlete_id,
            current_round=current_round,
        )
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/amministrazione/partecipanti",
    response_model=list[LeagueMemberResponse],
)
def list_league_members(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueMembershipService = Depends(get_league_membership_service),
) -> list[LeagueMemberResponse]:
    """List current league participants for league administration."""
    return service.list(league_access)


@router.post(
    "/{league_id}/amministrazione/partecipanti/{user_id}/trasferimento-admin",
    response_model=LeagueMemberResponse,
)
def transfer_league_admin(
    user_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueMembershipService = Depends(get_league_membership_service),
) -> LeagueMemberResponse | JSONResponse:
    """Atomically transfer league administration to another participant."""
    try:
        return service.transfer_admin(league_access, user_id)
    except AuthError as exc:
        return _error_response(exc)


@router.delete(
    "/{league_id}/amministrazione/partecipanti/{user_id}",
    response_model=LeagueMemberResponse,
)
def remove_league_member(
    user_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueMembershipService = Depends(get_league_membership_service),
) -> LeagueMemberResponse | JSONResponse:
    """Remove a non-admin participant while the league is in draft."""
    try:
        return service.remove(league_access, user_id)
    except AuthError as exc:
        return _error_response(exc)


@router.post(
    "/{league_id}/amministrazione/inviti",
    response_model=CreateLeagueInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_league_invite(
    body: CreateLeagueInviteRequest,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueInviteService = Depends(get_league_invite_service),
) -> CreateLeagueInviteResponse | JSONResponse:
    """Create an expiring, revocable invite for a draft league."""
    try:
        return service.create(league_access, body)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/amministrazione/inviti",
    response_model=list[LeagueInviteResponse],
)
def list_league_invites(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueInviteService = Depends(get_league_invite_service),
) -> list[LeagueInviteResponse]:
    return service.list(league_access)


@router.delete(
    "/{league_id}/amministrazione/inviti/{invite_id}",
    response_model=LeagueInviteResponse,
)
def revoke_league_invite(
    invite_id: UUID,
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_ADMIN)),
    service: LeagueInviteService = Depends(get_league_invite_service),
) -> LeagueInviteResponse | JSONResponse:
    """Revoke an invite; repeated revocation is idempotent."""
    try:
        return service.revoke(league_access, invite_id)
    except AuthError as exc:
        return _error_response(exc)


@router.get(
    "/{league_id}/classifica",
    response_model=list[LeagueStandingResponse],
)
def get_league_standings(
    league_access: LeagueAccess = Depends(require_league_permissions(Permission.LEAGUE_VIEW)),
    session: Session = Depends(get_db_session),
) -> list[LeagueStandingResponse]:
    """Classifica persistita (EP07-06), ordinata per posizione."""
    rows = list_league_standings(session, league_id=league_access.league.id)
    return [
        LeagueStandingResponse(
            fantasyTeamId=str(row.fantasy_team_id),
            position=row.position,
            played=row.played,
            won=row.won,
            drawn=row.drawn,
            lost=row.lost,
            fantasyGoalsFor=row.fantasy_goals_for,
            fantasyGoalsAgainst=row.fantasy_goals_against,
            points=row.points,
            computedAt=row.computed_at,
        )
        for row in rows
    ]
