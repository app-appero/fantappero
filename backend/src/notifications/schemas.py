"""HTTP schemas for the in-app notification center (EP09-01)."""

from __future__ import annotations

from pydantic import Field

from auth.schemas import ApiModel


class NotificationItemResponse(ApiModel):
    id: str
    category: str
    title: str
    body: str
    deep_link: str | None = Field(default=None, alias="deepLink")
    read: bool
    read_at: str | None = Field(default=None, alias="readAt")
    created_at: str = Field(alias="createdAt")


class NotificationListResponse(ApiModel):
    items: list[NotificationItemResponse]
    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    total_pages: int = Field(alias="totalPages")
    unread_count: int = Field(alias="unreadCount")


class MarkAllReadResponse(ApiModel):
    marked_count: int = Field(alias="markedCount")


class NotificationPreferenceItemResponse(ApiModel):
    category: str
    in_app_enabled: bool = Field(alias="inAppEnabled")


class NotificationPreferenceListResponse(ApiModel):
    items: list[NotificationPreferenceItemResponse]


class UpdateNotificationPreferenceRequest(ApiModel):
    category: str
    in_app_enabled: bool = Field(alias="inAppEnabled")
