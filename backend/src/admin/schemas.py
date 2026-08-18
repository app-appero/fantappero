"""Admin panel HTTP schemas — platform operator only (EP11-04a)."""

from __future__ import annotations

from datetime import datetime

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
