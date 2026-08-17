"""League listone view, overrides and provider refresh (EP04-04 / Asta UI)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from config.settings.loader import get_api_settings
from database.enums import FantasyRole, LeagueAuditAction
from leagues.listone_refresh_progress import (
    ListoneRefreshProgress,
    load_progress,
    new_job_id,
    save_progress,
)
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.schemas import (
    LeagueListoneEntryResponse,
    LeagueListoneOverrideResponse,
    LeagueListoneRefreshCounters,
    LeagueListoneRefreshJobResponse,
    LeagueListoneRefreshProgressResponse,
    LeagueListoneRefreshResponse,
)
from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.catalog.sync import sync_mvp_catalog_with_client
from sports_data.listone.generate import (
    generate_official_listone,
    get_role_assignment,
    list_role_assignments,
)
from sports_data.listone.mapping import MAPPING_VERSION
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.listone.overrides import (
    clear_override,
    create_override,
    effective_role_for_athlete,
    get_active_override,
    list_active_overrides,
    override_is_pending,
)
from sports_data.listone.validators import (
    ListoneValidationError,
    compute_override_effective_from_round,
    validate_fantasy_role,
)
from sports_data.provider.client import ApiFootballClient, build_client_from_settings
from sports_data.provider.constants import PROVIDER_NAME
from sports_data.provider.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
)
from sports_data.roster.models import Athlete
from sports_data.roster.sync import sync_mvp_roster_with_client

logger = get_logger(__name__)

LISTONE_OVERRIDE_WRITES_TOTAL = "listone_override_writes_total"
LISTONE_REFRESH_RUNS_TOTAL = "listone_refresh_runs_total"
LISTONE_REFRESH_DURATION_SECONDS = "listone_refresh_duration_seconds"


class LeagueListoneService:
    """Server-side listone reads, overrides and provider refresh for a private league."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_entries(
        self,
        league_access: LeagueAccess,
        *,
        current_round: int = 0,
    ) -> list[LeagueListoneEntryResponse]:
        league = league_access.league
        assignments = list_role_assignments(
            self._session,
            season_year=league.season_year,
        )
        overrides = {
            row.athlete_id: row
            for row in list_active_overrides(self._session, league_id=league.id)
        }
        athlete_ids = [row.athlete_id for row in assignments]
        athletes: dict[UUID, Athlete] = {}
        if athlete_ids:
            athletes = {
                row.id: row
                for row in self._session.execute(
                    select(Athlete).where(Athlete.id.in_(athlete_ids))
                )
                .scalars()
                .all()
            }
        club_ids = [row.club_id for row in assignments if row.club_id is not None]
        clubs: dict[UUID, Club] = {}
        if club_ids:
            clubs = {
                row.id: row
                for row in self._session.execute(select(Club).where(Club.id.in_(club_ids)))
                .scalars()
                .all()
            }

        entries: list[LeagueListoneEntryResponse] = []
        for assignment in assignments:
            athlete = athletes.get(assignment.athlete_id)
            override = overrides.get(assignment.athlete_id)
            club = clubs.get(assignment.club_id) if assignment.club_id else None
            effective = effective_role_for_athlete(
                official_role=assignment.role,
                override=override,
                current_round=current_round,
            )
            entries.append(
                self._to_entry(
                    assignment=assignment,
                    athlete=athlete,
                    club=club,
                    override=override,
                    effective_role=effective,
                    current_round=current_round,
                )
            )
        return entries

    def refresh_from_provider(
        self,
        league_access: LeagueAccess,
        *,
        client: ApiFootballClient | None = None,
        on_progress: Callable[[int, str, str], None] | None = None,
    ) -> LeagueListoneRefreshResponse:
        """Sync full MVP catalog + rosters from API-Football, then regenerate listone."""
        league = league_access.league
        metrics = get_metrics()
        status = "ok"
        owns_client = client is None

        def report(percent: int, stage: str, message: str) -> None:
            if on_progress is not None:
                on_progress(max(0, min(100, percent)), stage, message)

        with Timer(
            metrics,
            LISTONE_REFRESH_DURATION_SECONDS,
            labels={"provider": PROVIDER_NAME},
        ):
            try:
                if client is None:
                    try:
                        client = build_client_from_settings(get_api_settings())
                    except ProviderConfigError as exc:
                        raise ValidationAuthError(
                            "Chiave API-Football assente sul server. "
                            "Imposta API_FOOTBALL_KEY nell'ambiente backend.",
                            code="provider_key_missing",
                        ) from exc

                report(5, "catalog", "Sincronizzazione catalogo campionati e club…")
                sync_mvp_catalog_with_client(self._session, client)
                if self._count_clubs_for_season(league.season_year) == 0:
                    raise ValidationAuthError(
                        "Catalogo club non disponibile dopo il sync. "
                        "Verifica la stagione e la copertura provider.",
                        code="catalog_not_ready",
                    )
                report(12, "catalog", "Catalogo aggiornato. Avvio sync rose…")

                def roster_progress(done: int, total: int, label: str) -> None:
                    # Map roster work to 12% → 90%
                    ratio = done / total if total else 1.0
                    percent = 12 + int(ratio * 78)
                    report(
                        percent,
                        "roster",
                        f"Rosa {done}/{total}: {label}",
                    )

                roster_result = sync_mvp_roster_with_client(
                    self._session,
                    client,
                    season_year=league.season_year,
                    on_progress=roster_progress,
                )
                report(92, "listone", "Generazione listone ufficiale…")
                listone_result = generate_official_listone(
                    self._session,
                    season_year=league.season_year,
                )
                refreshed_at = datetime.now(UTC)
                counters = LeagueListoneRefreshCounters(
                    athletesCreated=roster_result.counters.athletes_created,
                    athletesUpdated=roster_result.counters.athletes_updated,
                    membershipsCreated=roster_result.counters.memberships_created,
                    membershipsUpdated=roster_result.counters.memberships_updated,
                    transfersCreated=roster_result.counters.transfers_created,
                    listoneCreated=listone_result.counters.created,
                    listoneUpdated=listone_result.counters.updated,
                    listoneUnchanged=listone_result.counters.unchanged,
                    listoneSkippedUnmapped=listone_result.counters.skipped_unmapped,
                    catalogSynced=True,
                )
                self._session.add(
                    LeagueAuditEvent(
                        league_id=league.id,
                        actor_id=league_access.user.id,
                        action=LeagueAuditAction.LEAGUE_LISTONE_REFRESHED,
                        details={
                            "seasonYear": league.season_year,
                            "mappingVersion": MAPPING_VERSION,
                            "catalogSynced": True,
                            "listoneCreated": counters.listone_created,
                            "listoneUpdated": counters.listone_updated,
                            "skippedUnmapped": counters.listone_skipped_unmapped,
                        },
                    )
                )
                self._session.flush()
                logger.info(
                    "listone_refresh_ok",
                    extra={
                        "league_id": str(league.id),
                        "season_year": league.season_year,
                        "catalog_synced": True,
                        "listone_created": counters.listone_created,
                        "listone_updated": counters.listone_updated,
                    },
                )
                report(100, "completed", "Listone aggiornato dal provider sportivo.")
                return LeagueListoneRefreshResponse(
                    seasonYear=league.season_year,
                    mappingVersion=MAPPING_VERSION,
                    refreshedAt=refreshed_at,
                    message="Listone aggiornato dal provider sportivo.",
                    counters=counters,
                )
            except ValidationAuthError:
                status = "error"
                raise
            except ProviderRateLimitError as exc:
                status = "error"
                raise ValidationAuthError(
                    "Quota API-Football esaurita o rate limit attivo. "
                    "Il sync MVP chiama molte richieste: attendi circa un minuto e riprova.",
                    code="provider_rate_limited",
                ) from exc
            except ProviderAuthError as exc:
                status = "error"
                raise ValidationAuthError(
                    "Autenticazione provider rifiutata. Verifica API_FOOTBALL_KEY.",
                    code="provider_auth_failed",
                ) from exc
            except ProviderError as exc:
                status = "error"
                logger.exception(
                    "listone_refresh_failed",
                    extra={"league_id": str(league.id), "season_year": league.season_year},
                )
                raise ValidationAuthError(
                    "Aggiornamento listone non riuscito dal provider sportivo.",
                    code="provider_sync_failed",
                ) from exc
            except Exception as exc:
                status = "error"
                logger.exception(
                    "listone_refresh_failed",
                    extra={"league_id": str(league.id), "season_year": league.season_year},
                )
                raise ValidationAuthError(
                    "Aggiornamento listone non riuscito.",
                    code="listone_refresh_failed",
                ) from exc
            finally:
                metrics.incr(
                    LISTONE_REFRESH_RUNS_TOTAL,
                    labels={"provider": PROVIDER_NAME, "status": status},
                )
                if owns_client and client is not None:
                    client.close()

    def start_refresh_job(self, league_access: LeagueAccess) -> LeagueListoneRefreshJobResponse:
        """Enqueue async listone refresh and return a pollable job id."""
        from leagues.listone_tasks import refresh_league_listone_task

        job_id = new_job_id()
        league_id = str(league_access.league.id)
        save_progress(
            ListoneRefreshProgress(
                job_id=job_id,
                league_id=league_id,
                status="queued",
                percent=0,
                stage="queued",
                message="Aggiornamento in coda…",
            )
        )
        refresh_league_listone_task.delay(
            job_id=job_id,
            league_id=league_id,
            actor_id=str(league_access.user.id),
        )
        return LeagueListoneRefreshJobResponse(
            jobId=job_id,
            status="queued",
            message="Aggiornamento listone avviato.",
        )

    def get_refresh_progress(
        self,
        league_access: LeagueAccess,
        job_id: str,
    ) -> LeagueListoneRefreshProgressResponse:
        progress = load_progress(job_id)
        if progress is None or progress.league_id != str(league_access.league.id):
            raise ValidationAuthError(
                "Job di aggiornamento non trovato.",
                code="listone_refresh_job_not_found",
            )
        result = None
        if progress.result is not None:
            result = LeagueListoneRefreshResponse.model_validate(progress.result)
        return LeagueListoneRefreshProgressResponse(
            jobId=progress.job_id,
            leagueId=progress.league_id,
            status=progress.status,
            percent=progress.percent,
            stage=progress.stage,
            message=progress.message,
            errorCode=progress.error_code,
            result=result,
        )
    def set_override(
        self,
        league_access: LeagueAccess,
        *,
        athlete_id: UUID,
        role: FantasyRole | str,
        current_round: int | None = None,
        reason: str | None = None,
    ) -> LeagueListoneEntryResponse:
        league = league_access.league
        try:
            fantasy_role = validate_fantasy_role(role)
            effective_from = compute_override_effective_from_round(
                league_state=league.state,
                current_round=current_round,
            )
        except ListoneValidationError as exc:
            raise ValidationAuthError(exc.message, code=exc.code) from exc

        assignment = get_role_assignment(
            self._session,
            athlete_id=athlete_id,
            season_year=league.season_year,
        )
        if assignment is None:
            raise ValidationAuthError(
                "Il calciatore non è presente nel listone ufficiale della stagione.",
                code="athlete_not_on_listone",
            )

        athlete = self._session.get(Athlete, athlete_id)
        if athlete is None:
            raise ValidationAuthError(
                "Calciatore non trovato.",
                code="athlete_not_found",
            )
        club = self._session.get(Club, assignment.club_id) if assignment.club_id else None

        row = create_override(
            self._session,
            league_id=league.id,
            athlete_id=athlete_id,
            role=fantasy_role,
            effective_from_round=effective_from,
            actor_id=league_access.user.id,
            reason=(reason.strip() if reason else None) or None,
        )
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_ROLE_OVERRIDE_SET,
                details={
                    "athleteId": str(athlete_id),
                    "role": fantasy_role.value,
                    "effectiveFromRound": effective_from,
                    "officialRole": assignment.role.value,
                },
            )
        )
        self._session.flush()
        get_metrics().incr(
            LISTONE_OVERRIDE_WRITES_TOTAL,
            labels={"provider": PROVIDER_NAME, "action": "set"},
        )
        logger.info(
            "listone_override_set",
            extra={
                "league_id": str(league.id),
                "athlete_id": str(athlete_id),
                "role": fantasy_role.value,
                "effective_from_round": effective_from,
                "league_state": league.state.value,
            },
        )

        round_for_view = 0 if current_round is None else current_round
        effective = effective_role_for_athlete(
            official_role=assignment.role,
            override=row,
            current_round=round_for_view,
        )
        return self._to_entry(
            assignment=assignment,
            athlete=athlete,
            club=club,
            override=row,
            effective_role=effective,
            current_round=round_for_view,
        )

    def clear_role_override(
        self,
        league_access: LeagueAccess,
        *,
        athlete_id: UUID,
        current_round: int = 0,
    ) -> LeagueListoneEntryResponse:
        league = league_access.league
        try:
            compute_override_effective_from_round(
                league_state=league.state,
                current_round=current_round,
            )
        except ListoneValidationError as exc:
            raise ValidationAuthError(exc.message, code=exc.code) from exc

        assignment = get_role_assignment(
            self._session,
            athlete_id=athlete_id,
            season_year=league.season_year,
        )
        if assignment is None:
            raise ValidationAuthError(
                "Il calciatore non è presente nel listone ufficiale della stagione.",
                code="athlete_not_on_listone",
            )

        cleared = clear_override(
            self._session,
            league_id=league.id,
            athlete_id=athlete_id,
        )
        if cleared is None:
            raise ValidationAuthError(
                "Non esiste un override attivo per questo calciatore.",
                code="role_override_not_found",
            )

        athlete = self._session.get(Athlete, athlete_id)
        club = self._session.get(Club, assignment.club_id) if assignment.club_id else None
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_ROLE_OVERRIDE_CLEARED,
                details={
                    "athleteId": str(athlete_id),
                    "previousRole": cleared.role.value,
                    "previousEffectiveFromRound": cleared.effective_from_round,
                },
            )
        )
        self._session.flush()
        get_metrics().incr(
            LISTONE_OVERRIDE_WRITES_TOTAL,
            labels={"provider": PROVIDER_NAME, "action": "clear"},
        )
        logger.info(
            "listone_override_cleared",
            extra={
                "league_id": str(league.id),
                "athlete_id": str(athlete_id),
                "league_state": league.state.value,
            },
        )
        return self._to_entry(
            assignment=assignment,
            athlete=athlete,
            club=club,
            override=None,
            effective_role=assignment.role,
            current_round=current_round,
        )

    def get_entry(
        self,
        league_access: LeagueAccess,
        *,
        athlete_id: UUID,
        current_round: int = 0,
    ) -> LeagueListoneEntryResponse:
        league = league_access.league
        assignment = get_role_assignment(
            self._session,
            athlete_id=athlete_id,
            season_year=league.season_year,
        )
        if assignment is None:
            raise ValidationAuthError(
                "Il calciatore non è presente nel listone ufficiale della stagione.",
                code="athlete_not_on_listone",
            )
        override = get_active_override(
            self._session,
            league_id=league.id,
            athlete_id=athlete_id,
        )
        athlete = self._session.get(Athlete, athlete_id)
        club = self._session.get(Club, assignment.club_id) if assignment.club_id else None
        effective = effective_role_for_athlete(
            official_role=assignment.role,
            override=override,
            current_round=current_round,
        )
        return self._to_entry(
            assignment=assignment,
            athlete=athlete,
            club=club,
            override=override,
            effective_role=effective,
            current_round=current_round,
        )

    def _count_clubs_for_season(self, season_year: int) -> int:
        return int(
            self._session.execute(
                select(func.count())
                .select_from(CompetitionSeasonClub)
                .join(SportSeason, CompetitionSeasonClub.sport_season_id == SportSeason.id)
                .where(SportSeason.year == season_year)
            ).scalar_one()
        )

    @staticmethod
    def _to_entry(
        *,
        assignment: RoleAssignment,
        athlete: Athlete | None,
        club: Club | None,
        override: LeagueRoleOverride | None,
        effective_role: FantasyRole,
        current_round: int,
    ) -> LeagueListoneEntryResponse:
        pending = override_is_pending(override=override, current_round=current_round)
        override_payload = None
        if override is not None:
            override_payload = LeagueListoneOverrideResponse(
                role=override.role.value,  # type: ignore[arg-type]
                effectiveFromRound=override.effective_from_round,
                pending=pending,
                reason=override.reason,
            )
        return LeagueListoneEntryResponse(
            athleteId=str(assignment.athlete_id),
            canonicalName=athlete.canonical_name if athlete else "",
            seasonYear=assignment.season_year,
            officialRole=assignment.role.value,  # type: ignore[arg-type]
            effectiveRole=effective_role.value,  # type: ignore[arg-type]
            providerPositionRaw=assignment.provider_position_raw,
            mappingVersion=assignment.mapping_version,
            clubId=str(assignment.club_id) if assignment.club_id else None,
            clubName=club.name if club else None,
            override=override_payload,
        )
