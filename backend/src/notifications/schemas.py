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


class NotificationEventPreferenceItemResponse(ApiModel):
    """Preferenza granulare per singolo evento (TASK5), canali separati."""

    event_key: str = Field(alias="eventKey")
    category: str
    label: str
    in_app_enabled: bool = Field(alias="inAppEnabled")
    push_enabled: bool = Field(alias="pushEnabled")


class NotificationPreferenceListResponse(ApiModel):
    items: list[NotificationPreferenceItemResponse]
    #: Preferenze granulari per evento (TASK5). Lista aggiuntiva, additiva:
    #: ``items`` resta per compatibilità con chi legge solo la categoria.
    events: list[NotificationEventPreferenceItemResponse] = Field(default_factory=list)


class UpdateNotificationPreferenceRequest(ApiModel):
    """Corpo del ``PUT /notifications/preferences``.

    Due forme, selezionate dal campo presente:
    - per categoria (compatibilità, EP09-01): ``{"category": ..., "inAppEnabled": ...}``
    - granulare per evento (TASK5): ``{"eventKey": ..., "inAppEnabled": ..., "pushEnabled": ...}``
      (almeno uno dei due booleani; l'altro resta invariato)
    """

    category: str | None = None
    event_key: str | None = Field(default=None, alias="eventKey")
    in_app_enabled: bool | None = Field(default=None, alias="inAppEnabled")
    push_enabled: bool | None = Field(default=None, alias="pushEnabled")


class RegisterPushDeviceRequest(ApiModel):
    token: str = Field(min_length=1, max_length=255)
    platform: str = Field(min_length=1, max_length=16)


class PushDeviceResponse(ApiModel):
    id: str
    platform: str
