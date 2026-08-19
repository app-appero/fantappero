"""HTTP schemas for the market history feed (EP08-08 / FR-MKT-04)."""

from __future__ import annotations

from pydantic import Field

from auth.schemas import ApiModel


class MarketHistoryEntryResponse(ApiModel):
    id: str
    occurred_at: str = Field(alias="occurredAt")
    category: str
    action: str
    actor_id: str = Field(alias="actorId")
    details: dict[str, object] | None = None


class MarketHistoryListResponse(ApiModel):
    items: list[MarketHistoryEntryResponse]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    total_pages: int = Field(alias="totalPages")
