"""Admin panel: platform-wide listone view + provider refresh (EP11-04b).

The refresh orchestration here is intentionally standalone from
``LeagueListoneService.refresh_from_provider`` rather than extracted from it:
that method's exact call sequence (including the ``_count_clubs_for_season``
instance method) is monkeypatched by
``tests/unit/leagues/test_listone_refresh.py``, so refactoring it to share
code with a league-agnostic caller risked breaking those patches for no
functional gain. Both call the same lower-level sync/generate primitives.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from admin.schemas import (
    AdminListoneEntryResponse,
    AdminListoneRefreshCounters,
    AdminListoneRefreshJobResponse,
    AdminListoneRefreshProgressResponse,
    AdminListoneRefreshResultResponse,
)
from auth.exceptions import ValidationAuthError
from auth.models.user import User
from config.settings.api import ApiSettings
from config.settings.loader import get_api_settings
from leagues.listone_refresh_progress import (
    ListoneRefreshProgress,
    load_progress,
    new_job_id,
    save_progress,
)
from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.catalog.sync import sync_mvp_catalog_with_client
from sports_data.listone.generate import generate_official_listone, list_role_assignments
from sports_data.listone.mapping import MAPPING_VERSION
from sports_data.listone.models import RoleAssignment
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

PLATFORM_JOB_SCOPE = "platform"
LISTONE_PLATFORM_REFRESH_RUNS_TOTAL = "listone_platform_refresh_runs_total"
LISTONE_PLATFORM_REFRESH_DURATION_SECONDS = "listone_platform_refresh_duration_seconds"

_logger = get_logger(__name__)


def _count_clubs_for_season(session: Session, season_year: int) -> int:
    return int(
        session.execute(
            select(func.count())
            .select_from(CompetitionSeasonClub)
            .join(SportSeason, CompetitionSeasonClub.sport_season_id == SportSeason.id)
            .where(SportSeason.year == season_year)
        ).scalar_one()
    )


def refresh_platform_listone(
    session: Session,
    *,
    season_year: int,
    client: ApiFootballClient | None = None,
    on_progress: Callable[[int, str, str], None] | None = None,
) -> AdminListoneRefreshResultResponse:
    """Sync full MVP catalog + rosters from API-Football, then regenerate the listone."""
    metrics = get_metrics()
    status = "ok"
    owns_client = client is None

    def report(percent: int, stage: str, message: str) -> None:
        if on_progress is not None:
            on_progress(max(0, min(100, percent)), stage, message)

    with Timer(
        metrics,
        LISTONE_PLATFORM_REFRESH_DURATION_SECONDS,
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
            sync_mvp_catalog_with_client(session, client)
            if _count_clubs_for_season(session, season_year) == 0:
                raise ValidationAuthError(
                    "Catalogo club non disponibile dopo il sync. "
                    "Verifica la stagione e la copertura provider.",
                    code="catalog_not_ready",
                )
            report(12, "catalog", "Catalogo aggiornato. Avvio sync rose…")

            def roster_progress(done: int, total: int, label: str) -> None:
                ratio = done / total if total else 1.0
                percent = 12 + int(ratio * 78)
                report(percent, "roster", f"Rosa {done}/{total}: {label}")

            roster_result = sync_mvp_roster_with_client(
                session,
                client,
                season_year=season_year,
                on_progress=roster_progress,
            )
            report(92, "listone", "Generazione listone ufficiale…")
            listone_result = generate_official_listone(session, season_year=season_year)
            refreshed_at = datetime.now(UTC)
            counters = AdminListoneRefreshCounters(
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
            session.flush()
            _logger.info(
                "listone_platform_refresh_ok",
                extra={
                    "event": "admin_listone_refreshed",
                    "season_year": season_year,
                    "listone_created": counters.listone_created,
                    "listone_updated": counters.listone_updated,
                },
            )
            report(100, "completed", "Listone aggiornato dal provider sportivo.")
            return AdminListoneRefreshResultResponse(
                seasonYear=season_year,
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
            _logger.exception(
                "listone_platform_refresh_failed",
                extra={"season_year": season_year},
            )
            raise ValidationAuthError(
                "Aggiornamento listone non riuscito dal provider sportivo.",
                code="provider_sync_failed",
            ) from exc
        except Exception as exc:
            status = "error"
            _logger.exception(
                "listone_platform_refresh_failed",
                extra={"season_year": season_year},
            )
            raise ValidationAuthError(
                "Aggiornamento listone non riuscito.",
                code="listone_refresh_failed",
            ) from exc
        finally:
            metrics.incr(
                LISTONE_PLATFORM_REFRESH_RUNS_TOTAL,
                labels={"provider": PROVIDER_NAME, "status": status},
            )
            if owns_client and client is not None:
                client.close()


def _to_entry(
    assignment: RoleAssignment,
    athlete: Athlete | None,
    club: Club | None,
) -> AdminListoneEntryResponse:
    return AdminListoneEntryResponse(
        athleteId=str(assignment.athlete_id),
        canonicalName=athlete.canonical_name if athlete else "",
        seasonYear=assignment.season_year,
        officialRole=assignment.role.value,  # type: ignore[arg-type]
        providerPositionRaw=assignment.provider_position_raw,
        mappingVersion=assignment.mapping_version,
        clubId=str(assignment.club_id) if assignment.club_id else None,
        clubName=club.name if club else None,
    )


class AdminListoneService:
    """Read-only platform listone view + provider refresh trigger (EP11-04b)."""

    def __init__(self, session: Session, settings: ApiSettings) -> None:
        self._session = session
        self._settings = settings

    def list_entries(self, *, season_year: int) -> list[AdminListoneEntryResponse]:
        assignments = list_role_assignments(self._session, season_year=season_year)
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
        return [
            _to_entry(
                assignment,
                athletes.get(assignment.athlete_id),
                clubs.get(assignment.club_id) if assignment.club_id else None,
            )
            for assignment in assignments
        ]

    def start_refresh_job(
        self, *, season_year: int, actor: User
    ) -> AdminListoneRefreshJobResponse:
        from admin.listone_tasks import refresh_platform_listone_task

        job_id = new_job_id()
        save_progress(
            ListoneRefreshProgress(
                job_id=job_id,
                league_id=PLATFORM_JOB_SCOPE,
                status="queued",
                percent=0,
                stage="queued",
                message="Aggiornamento in coda…",
            )
        )
        refresh_platform_listone_task.delay(
            job_id=job_id,
            season_year=season_year,
            actor_id=str(actor.id),
        )
        return AdminListoneRefreshJobResponse(
            jobId=job_id,
            status="queued",
            message="Aggiornamento listone avviato.",
        )

    def get_refresh_progress(self, *, job_id: str) -> AdminListoneRefreshProgressResponse:
        progress = load_progress(job_id)
        if progress is None or progress.league_id != PLATFORM_JOB_SCOPE:
            raise ValidationAuthError(
                "Job di aggiornamento non trovato.",
                code="listone_refresh_job_not_found",
            )
        result = None
        if progress.result is not None:
            result = AdminListoneRefreshResultResponse.model_validate(progress.result)
        return AdminListoneRefreshProgressResponse(
            jobId=progress.job_id,
            status=progress.status,
            percent=progress.percent,
            stage=progress.stage,
            message=progress.message,
            errorCode=progress.error_code,
            result=result,
        )
