"""HTTP schemas for the league audit log view (EP11-03)."""

from __future__ import annotations

from pydantic import Field

from auth.schemas import ApiModel


class AuditLogEntryResponse(ApiModel):
    id: str
    occurred_at: str = Field(alias="occurredAt")
    actor_id: str = Field(alias="actorId")
    actor_display_name: str | None = Field(default=None, alias="actorDisplayName")
    action: str
    details: dict[str, object] | None = None


class AuditLogListResponse(ApiModel):
    items: list[AuditLogEntryResponse]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    total_pages: int = Field(alias="totalPages")
