"""Admin panel HTTP schemas — platform operator only (EP11-04a / EP11-04b)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from app.text_validation import AthleteNameStr, NoNulStr
from auth.schemas import ApiModel, SessionUserResponse
from database.enums import LeagueState, PlatformRole


class AdminOverviewResponse(ApiModel):
    operator_id: str = Field(alias="operatorId")
    operator_display_name: str = Field(alias="operatorDisplayName")
    environment: str
    users_count: int = Field(alias="usersCount")
    operators_count: int = Field(alias="operatorsCount")
    leagues_count: int = Field(alias="leaguesCount")
    #: Riepilogo 1.4: leghe per stato (`draft`, `active`, …). Vuoto dai server più vecchi.
    leagues_by_state: dict[str, int] = Field(default_factory=dict, alias="leaguesByState")
    #: Riepilogo 1.4: le cose da guardare. Assente dai server più vecchi.
    watch: AdminWatchResponse | None = None


class AdminUserResponse(ApiModel):
    id: str
    email: str
    display_name: str = Field(alias="displayName")
    platform_role: PlatformRole = Field(alias="platformRole")
    created_at: datetime = Field(alias="createdAt")
    #: Autorizzato in modalità test (in lista, oppure operatore: tester di default).
    is_tester: bool = Field(default=False, alias="isTester")
    #: Operatore protetto: non può essere declassato, eliminato o bloccato.
    is_protected: bool = Field(default=False, alias="isProtected")
    #: A quante leghe partecipa (serve ad avvisare prima di eliminare l'utente).
    league_count: int = Field(default=0, alias="leagueCount")


class AdminTesterResponse(ApiModel):
    id: str
    email: str
    #: Nome dell'account se la persona ha già acceduto.
    display_name: str | None = Field(default=None, alias="displayName")
    created_at: datetime = Field(alias="createdAt")


class AdminTestModeResponse(ApiModel):
    enabled: bool
    testers: list[AdminTesterResponse]


class AdminTestModeUpdateRequest(ApiModel):
    enabled: bool


class AdminAddTesterRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)


class AdminImpersonateResponse(ApiModel):
    """Token di accesso a scadenza breve per debug di supporto (no refresh token:
    la sessione impersonata non si rinnova, scade da sola in pochi minuti)."""

    access_token: str = Field(alias="accessToken")
    expires_in: int = Field(alias="expiresIn")
    user: SessionUserResponse


class AdminImpersonationRevokeResponse(ApiModel):
    """Esito della revoca immediata: quanti token di impersonazione attivi sono stati chiusi."""

    revoked_count: int = Field(alias="revokedCount")


class PaginatedAdminUsersResponse(ApiModel):
    items: list[AdminUserResponse]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    total_pages: int = Field(alias="totalPages")


class AdminLeagueResponse(ApiModel):
    id: str
    name: str
    state: LeagueState
    owner_display_name: str | None = Field(default=None, alias="ownerDisplayName")
    created_at: datetime = Field(alias="createdAt")


class PaginatedAdminLeaguesResponse(ApiModel):
    items: list[AdminLeagueResponse]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    total_pages: int = Field(alias="totalPages")


class AdminLeagueTurnStatusResponse(ApiModel):
    """Riga di sintesi per la scelta di un'azione puntuale (EP-turni-automazione)."""

    league_id: str = Field(alias="leagueId")
    league_name: str = Field(alias="leagueName")
    current_round_id: str | None = Field(default=None, alias="currentRoundId")
    current_round_number: int | None = Field(default=None, alias="currentRoundNumber")
    current_round_status: str | None = Field(default=None, alias="currentRoundStatus")
    homologation_status: str | None = Field(default=None, alias="homologationStatus")
    calendar_updated_at: datetime | None = Field(default=None, alias="calendarUpdatedAt")


class AdminTurniSyncResultResponse(ApiModel):
    """Esito di `ensure_upcoming_for_active_leagues` innescato a mano."""

    leagues: int
    created: int
    opened: int
    upgraded: int
    duplicates: int
    waiting: int


class AdminAiLineupsSyncResultResponse(ApiModel):
    """Esito di `generate_ai_lineups_for_active_leagues` innescato a mano."""

    rounds: int
    teams_updated: int = Field(alias="teamsUpdated")
    teams_skipped: int = Field(alias="teamsSkipped")


class AdminCalendarSyncJobResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    message: str


class AdminCalendarSyncResultResponse(ApiModel):
    """Esito di `refresh_full_calendar_for_active_leagues` innescato a mano."""

    leagues: int
    refreshed: int
    failed: int
    fixtures_created: int = Field(alias="fixturesCreated")
    fixtures_updated: int = Field(alias="fixturesUpdated")
    rounds_realigned: int = Field(alias="roundsRealigned")
    rounds_removed: int = Field(alias="roundsRemoved")


class AdminCalendarSyncProgressResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    percent: int
    stage: str
    message: str
    error_code: str | None = Field(default=None, alias="errorCode")
    result: AdminCalendarSyncResultResponse | None = None


class AdminSeasonImportJobResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    message: str


class AdminSeasonImportResultResponse(ApiModel):
    """Esito di "Importa calendario stagione" (catalogo + fixture, tutte le MVP)."""

    seasons_created: int = Field(alias="seasonsCreated")
    seasons_updated: int = Field(alias="seasonsUpdated")
    competitions_updated: int = Field(alias="competitionsUpdated")
    fixtures_created: int = Field(alias="fixturesCreated")
    fixtures_updated: int = Field(alias="fixturesUpdated")


class AdminSeasonImportProgressResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    percent: int
    stage: str
    message: str
    error_code: str | None = Field(default=None, alias="errorCode")
    result: AdminSeasonImportResultResponse | None = None


class AdminResultRecoveryJobResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    message: str


class AdminResultRecoveryResultResponse(ApiModel):
    """Esito di `recover_stale_match_results` (risultati arretrati + calcolo)."""

    fixtures_created: int = Field(alias="fixturesCreated")
    fixtures_updated: int = Field(alias="fixturesUpdated")
    details_fetched: int = Field(alias="detailsFetched")
    rounds_considered: int = Field(alias="roundsConsidered")
    rounds_processed: int = Field(alias="roundsProcessed")
    rounds_finalized: int = Field(alias="roundsFinalized")
    fixtures_scored: int = Field(alias="fixturesScored")
    errors: list[dict[str, str]] = Field(default_factory=list)


class AdminResultRecoveryProgressResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    percent: int
    stage: str
    message: str
    error_code: str | None = Field(default=None, alias="errorCode")
    result: AdminResultRecoveryResultResponse | None = None


class AdminRoundCalculationResultResponse(ApiModel):
    """Esito di `process_live_fantasy_rounds` innescato a mano (EP-turni-calcolo)."""

    rounds_considered: int = Field(alias="roundsConsidered")
    rounds_processed: int = Field(alias="roundsProcessed")
    rounds_finalized: int = Field(alias="roundsFinalized")
    fixtures_scored: int = Field(alias="fixturesScored")
    errors: list[dict[str, str]] = Field(default_factory=list)


class AdminHistoricalRepairRequest(ApiModel):
    # Come per la correzione di un turno: niente NUL né surrogati nel motivo (QA 19/11).
    reason: NoNulStr = Field(min_length=1)


class AdminHistoricalRepairJobResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    message: str


class AdminHistoricalRepairResultResponse(ApiModel):
    """Esito di `repair_historical_rounds_for_active_leagues` (EP-turni-calcolo)."""

    leagues: int
    rounds_considered: int = Field(alias="roundsConsidered")
    rounds_repaired: int = Field(alias="roundsRepaired")
    rounds_failed: int = Field(alias="roundsFailed")
    errors: list[dict[str, str]] = Field(default_factory=list)


class AdminHistoricalRepairProgressResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    percent: int
    stage: str
    message: str
    error_code: str | None = Field(default=None, alias="errorCode")
    result: AdminHistoricalRepairResultResponse | None = None


class AdminListoneEntryResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    canonical_name: AthleteNameStr = Field(alias="canonicalName")
    season_year: int = Field(alias="seasonYear")
    official_role: Literal["P", "D", "C", "A"] = Field(alias="officialRole")
    provider_position_raw: str | None = Field(default=None, alias="providerPositionRaw")
    mapping_version: str = Field(alias="mappingVersion")
    club_id: str | None = Field(default=None, alias="clubId")
    club_name: str | None = Field(default=None, alias="clubName")


class AdminListoneRefreshCounters(ApiModel):
    athletes_created: int = Field(alias="athletesCreated")
    athletes_updated: int = Field(alias="athletesUpdated")
    memberships_created: int = Field(alias="membershipsCreated")
    memberships_updated: int = Field(alias="membershipsUpdated")
    transfers_created: int = Field(alias="transfersCreated")
    listone_created: int = Field(alias="listoneCreated")
    listone_updated: int = Field(alias="listoneUpdated")
    listone_unchanged: int = Field(alias="listoneUnchanged")
    listone_skipped_unmapped: int = Field(alias="listoneSkippedUnmapped")
    #: Ruoli che il fornitore cambierebbe ma che restano quelli del listone (congelati).
    role_changes_skipped: int = Field(default=0, alias="roleChangesSkipped")
    #: Calciatori tolti dal listone (non più in una rosa del fornitore), release 1.4.
    listone_removed: int = Field(default=0, alias="listoneRemoved")
    catalog_synced: bool = Field(alias="catalogSynced")


# --- ruoli del listone: ripristino e ruoli dal fornitore (22/11) -----------------------------

ListoneRoleCode = Literal["P", "D", "C", "A"]


class AdminListoneRoleRestoreRequest(ApiModel):
    season_year: int = Field(alias="seasonYear", ge=2000, le=2100)
    #: Momento prima dell'aggiornamento da annullare. Senza fuso orario vale come UTC.
    before: datetime
    dry_run: bool = Field(default=True, alias="dryRun")
    #: Solo questi calciatori (quelli dell'anteprima confermata); senza, tutti i candidati.
    athlete_ids: list[str] | None = Field(default=None, alias="athleteIds", max_length=10_000)

    @field_validator("before")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class AdminListoneRoleRestoreEntry(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    name: AthleteNameStr
    club: str | None = None
    current_role: ListoneRoleCode = Field(alias="currentRole")
    #: ``None`` se le risposte salvate prima di ``before`` non permettono di ricostruirlo.
    restored_role: ListoneRoleCode | None = Field(default=None, alias="restoredRole")
    reconstructible: bool
    restored_position: str | None = Field(default=None, alias="restoredPosition")
    restored_club: str | None = Field(default=None, alias="restoredClub")
    #: ``squads`` (rosa del club) o ``players`` (statistiche).
    restored_source: str | None = Field(default=None, alias="restoredSource")
    in_rosters: list[str] = Field(default_factory=list, alias="inRosters")


class AdminListoneRoleRestoreCounts(ApiModel):
    to_restore: int = Field(alias="toRestore")
    not_reconstructible: int = Field(alias="notReconstructible")
    restored: int
    rosters_over_quota_now: int = Field(alias="rostersOverQuotaNow")
    rosters_over_quota_after: int = Field(alias="rostersOverQuotaAfter")
    rosters_resynced: int = Field(alias="rostersResynced")


class AdminListoneRoleRestoreResponse(ApiModel):
    season_year: int = Field(alias="seasonYear")
    before: datetime
    dry_run: bool = Field(alias="dryRun")
    entries: list[AdminListoneRoleRestoreEntry]
    counts: AdminListoneRoleRestoreCounts


class AdminListoneProviderRolesRequest(ApiModel):
    season_year: int = Field(alias="seasonYear", ge=2000, le=2100)
    dry_run: bool = Field(default=True, alias="dryRun")
    #: Solo questi calciatori (quelli dell'anteprima confermata); senza, tutti.
    athlete_ids: list[str] | None = Field(default=None, alias="athleteIds", max_length=10_000)


class AdminListoneProviderRoleEntry(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    name: AthleteNameStr
    club: str | None = None
    current_role: ListoneRoleCode = Field(alias="currentRole")
    new_role: ListoneRoleCode = Field(alias="newRole")
    provider_position_raw: str | None = Field(default=None, alias="providerPositionRaw")
    in_rosters: list[str] = Field(default_factory=list, alias="inRosters")


class AdminListoneProviderRolesCounts(ApiModel):
    changes: int
    applied: int
    rosters_over_quota_now: int = Field(alias="rostersOverQuotaNow")
    rosters_over_quota_after: int = Field(alias="rostersOverQuotaAfter")
    rosters_resynced: int = Field(alias="rostersResynced")


class AdminListoneProviderRolesResponse(ApiModel):
    season_year: int = Field(alias="seasonYear")
    dry_run: bool = Field(alias="dryRun")
    entries: list[AdminListoneProviderRoleEntry]
    counts: AdminListoneProviderRolesCounts


class AdminListoneRefreshResultResponse(ApiModel):
    season_year: int = Field(alias="seasonYear")
    mapping_version: str = Field(alias="mappingVersion")
    refreshed_at: datetime = Field(alias="refreshedAt")
    message: str
    counters: AdminListoneRefreshCounters
    #: Con «Aggiorna anche i ruoli dal fornitore» (``updateRoles``): l'anteprima dei ruoli che
    #: cambierebbero, da confermare con ``POST /admin/listone/ruoli-dal-fornitore``.
    role_changes: AdminListoneProviderRolesResponse | None = Field(
        default=None, alias="roleChanges"
    )


class AdminListoneRefreshJobResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    message: str


class AdminListoneRefreshProgressResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    percent: int
    stage: str
    message: str
    error_code: str | None = Field(default=None, alias="errorCode")
    result: AdminListoneRefreshResultResponse | None = None


class AdminPendingTransferResponse(ApiModel):
    """Trasferimento Loan/N.D. in attesa di conferma amministrativa (OQ-12)."""

    id: str
    athlete_id: str = Field(alias="athleteId")
    athlete_name: AthleteNameStr = Field(alias="athleteName")
    transfer_date: str = Field(alias="transferDate")
    from_club_name: str | None = Field(default=None, alias="fromClubName")
    to_club_name: str | None = Field(default=None, alias="toClubName")
    transfer_type: str = Field(alias="transferType")
    created_at: datetime = Field(alias="createdAt")


class PaginatedAdminPendingTransfersResponse(ApiModel):
    items: list[AdminPendingTransferResponse]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    total_pages: int = Field(alias="totalPages")


class AdminTransferReviewedResponse(ApiModel):
    id: str
    reviewed_at: datetime = Field(alias="reviewedAt")
    reviewed_by_user_id: str = Field(alias="reviewedByUserId")


class AdminPredictedHintDiagnosisResponse(ApiModel):
    """Perché un atleta ha (o non ha) un indizio di formazione probabile."""

    athlete_id: str = Field(alias="athleteId")
    athlete_name: AthleteNameStr = Field(alias="athleteName")
    club_name: str | None = Field(default=None, alias="clubName")
    fixture_id: str | None = Field(default=None, alias="fixtureId")
    hint: Literal["starter", "bench", "unavailable"] | None = None
    reason: Literal[
        "hinted",
        "no_active_squad",
        "no_fixture_in_round",
        "no_snapshot_yet",
        "snapshot_not_usable",
        "unmapped_in_snapshot",
    ]
    detail: str
    similar_unmatched_names: list[str] = Field(default_factory=list, alias="similarUnmatchedNames")


class AdminBlockedAccountResponse(ApiModel):
    id: str
    email: str
    reason: str | None = None
    created_at: datetime = Field(alias="createdAt")


class AdminBlocklistResponse(ApiModel):
    items: list[AdminBlockedAccountResponse]


class AdminAddBlockedRequest(ApiModel):
    email: str = Field(min_length=3, max_length=320)
    reason: str | None = Field(default=None, max_length=500)


class AdminDeleteUserRequest(ApiModel):
    #: True = elimina e mette l'email in lista nera; False = elimina e basta.
    block: bool = True


class AdminDeleteUserResponse(ApiModel):
    deleted_user_id: str = Field(alias="deletedUserId")
    #: Email messa in lista nera; None se l'utente è stato eliminato senza bloccarlo.
    blocked_email: str | None = Field(default=None, alias="blockedEmail")


class AdminTesterRequestResponse(ApiModel):
    id: str
    email: str
    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    phone: str | None = None
    motivation: str | None = None
    status: str
    created_at: datetime = Field(alias="createdAt")
    decided_at: datetime | None = Field(default=None, alias="decidedAt")
    decision_note: str | None = Field(default=None, alias="decisionNote")


class AdminTesterRequestListResponse(ApiModel):
    requests: list[AdminTesterRequestResponse]


class AdminTesterRequestDecisionRequest(ApiModel):
    note: str | None = Field(default=None, max_length=500)


class AdminTesterRequestBulkRequest(ApiModel):
    ids: list[str] = Field(min_length=1, max_length=200)
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=500)


# --- versione dell'app Android (avviso «nuova versione disponibile») ---------------------------
#: Il versionCode più alto accettato da Android.
ANDROID_MAX_VERSION_CODE = 2_100_000_000


class AndroidAppVersionResponse(ApiModel):
    latest_version_name: str = Field(alias="latestVersionName")
    latest_version_code: int = Field(alias="latestVersionCode")
    download_url: str = Field(alias="downloadUrl")
    message: str | None = None


class AppVersionResponse(ApiModel):
    #: Ultima versione pubblicata dell'app Android; None se l'operatore non l'ha impostata.
    android: AndroidAppVersionResponse | None = None


class AdminAndroidAppVersionUpdateRequest(ApiModel):
    latest_version_name: NoNulStr = Field(
        alias="latestVersionName",
        min_length=1,
        max_length=32,
        pattern=r"^\s*[0-9]+(\.[0-9]+){0,3}\s*$",
    )
    latest_version_code: int = Field(
        alias="latestVersionCode", ge=1, le=ANDROID_MAX_VERSION_CODE, strict=True
    )
    download_url: NoNulStr = Field(alias="downloadUrl", min_length=9, max_length=500)
    message: NoNulStr | None = Field(default=None, max_length=200)

    @field_validator("latest_version_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("download_url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        url = value.strip()
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or any(ch.isspace() for ch in url):
            raise ValueError("Il link deve essere un indirizzo https://")
        return url

    @field_validator("message")
    @classmethod
    def _blank_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


# --- Riepilogo del pannello operatore: «Da guardare» (release 1.4, Rosario 22/11) ----------


class AdminWatchJobResponse(ApiModel):
    key: str
    title: str


class AdminWatchJobFailureResponse(ApiModel):
    """Un job con giri finiti con errore nel periodo guardato (l'errore più recente)."""

    job_key: str = Field(alias="jobKey")
    title: str
    failed_at: datetime = Field(alias="failedAt")
    reason: str | None = None
    #: Quanti giri finiti con errore nel periodo.
    failures: int
    #: Esito dell'ultimo giro, anche se successivo all'errore: ``ok`` = il job è già ripreso.
    last_outcome: Literal["ok", "failed"] = Field(alias="lastOutcome")
    last_finished_at: datetime = Field(alias="lastFinishedAt")


class AdminListoneUpdateResponse(ApiModel):
    """Ultimo aggiornamento del listone, salvato per sempre in ``listone_updates``."""

    updated_at: datetime = Field(alias="updatedAt")
    season_year: int = Field(alias="seasonYear")
    kind: Literal["refresh", "roles_from_provider", "roles_restored"]
    #: ``operator`` dal pannello operatore, ``league`` dalla pagina di una lega.
    source: Literal["operator", "league"]
    author_display_name: str | None = Field(default=None, alias="authorDisplayName")
    league_name: str | None = Field(default=None, alias="leagueName")
    added: int
    removed: int
    changed: int


class AdminCurrentRoundsResponse(ApiModel):
    """Giornate in corso (turno aperto o bloccato con la finestra non finita) nelle leghe attive."""

    active_leagues: int = Field(alias="activeLeagues")
    leagues_in_progress: int = Field(alias="leaguesInProgress")
    round_numbers: list[int] = Field(default_factory=list, alias="roundNumbers")


class AdminNextLineupLockResponse(ApiModel):
    """Il prossimo blocco delle formazioni fra tutte le leghe attive."""

    lock_at: datetime = Field(alias="lockAt")
    league_id: str = Field(alias="leagueId")
    league_name: str = Field(alias="leagueName")
    round_number: int = Field(alias="roundNumber")


class AdminWatchResponse(ApiModel):
    generated_at: datetime = Field(alias="generatedAt")
    tester_requests_pending: int = Field(alias="testerRequestsPending")
    oldest_tester_request_at: datetime | None = Field(default=None, alias="oldestTesterRequestAt")
    feedback_new: int = Field(alias="feedbackNew")
    latest_feedback_at: datetime | None = Field(default=None, alias="latestFeedbackAt")
    jobs_disabled: list[AdminWatchJobResponse] = Field(default_factory=list, alias="jobsDisabled")
    #: Da quando si guardano gli errori dei job (oggi: le ultime 24 ore).
    job_failures_since: datetime = Field(alias="jobFailuresSince")
    job_failures: list[AdminWatchJobFailureResponse] = Field(
        default_factory=list, alias="jobFailures"
    )
    listone_last_update: AdminListoneUpdateResponse | None = Field(
        default=None, alias="listoneLastUpdate"
    )
    current_rounds: AdminCurrentRoundsResponse = Field(alias="currentRounds")
    next_lineup_lock: AdminNextLineupLockResponse | None = Field(
        default=None, alias="nextLineupLock"
    )
    android_app_version: AndroidAppVersionResponse | None = Field(
        default=None, alias="androidAppVersion"
    )
