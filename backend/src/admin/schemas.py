"""Admin panel HTTP schemas — platform operator only (EP11-04a / EP11-04b)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from auth.schemas import ApiModel
from database.enums import LeagueState, PlatformRole


class AdminOverviewResponse(ApiModel):
    operator_id: str = Field(alias="operatorId")
    operator_display_name: str = Field(alias="operatorDisplayName")
    environment: str
    users_count: int = Field(alias="usersCount")
    operators_count: int = Field(alias="operatorsCount")
    leagues_count: int = Field(alias="leaguesCount")


class AdminUserResponse(ApiModel):
    id: str
    email: str
    display_name: str = Field(alias="displayName")
    platform_role: PlatformRole = Field(alias="platformRole")
    created_at: datetime = Field(alias="createdAt")


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


class AdminListoneEntryResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    canonical_name: str = Field(alias="canonicalName")
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
    catalog_synced: bool = Field(alias="catalogSynced")


class AdminListoneRefreshResultResponse(ApiModel):
    season_year: int = Field(alias="seasonYear")
    mapping_version: str = Field(alias="mappingVersion")
    refreshed_at: datetime = Field(alias="refreshedAt")
    message: str
    counters: AdminListoneRefreshCounters


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
