"""Schemi API delle segnalazioni utente."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from auth.schemas import ApiModel

FeedbackCategory = Literal["bug", "suggerimento", "altro"]
FeedbackStatus = Literal["new", "in_review", "resolved", "dismissed"]
FeedbackPlatform = Literal["web", "android", "ios"]


class FeedbackReportSummaryResponse(ApiModel):
    """Vista dell'autore sulle proprie segnalazioni: niente dati interni degli operatori."""

    id: str
    category: FeedbackCategory
    message: str
    status: FeedbackStatus
    created_at: datetime = Field(alias="createdAt")
    attachment_count: int = Field(alias="attachmentCount")


class FeedbackAttachmentResponse(ApiModel):
    id: str
    kind: Literal["image", "video"]
    content_type: str = Field(alias="contentType")
    size_bytes: int = Field(alias="sizeBytes")
    # Link firmato e a scadenza: <img>/<video> non possono mandare l'header Authorization.
    url: str


class FeedbackAdminReportResponse(ApiModel):
    id: str
    category: FeedbackCategory
    message: str
    status: FeedbackStatus
    created_at: datetime = Field(alias="createdAt")
    author_user_id: str = Field(alias="authorUserId")
    author_name: str = Field(alias="authorName")
    author_email: str = Field(alias="authorEmail")
    page_context: str | None = Field(alias="pageContext")
    platform: FeedbackPlatform | None
    app_version: str | None = Field(alias="appVersion")
    user_agent: str | None = Field(alias="userAgent")
    operator_note: str | None = Field(alias="operatorNote")
    handled_at: datetime | None = Field(alias="handledAt")
    attachments: list[FeedbackAttachmentResponse]


class FeedbackAdminListResponse(ApiModel):
    items: list[FeedbackAdminReportResponse]
    total: int
    new_count: int = Field(alias="newCount")
    page: int
    page_size: int = Field(alias="pageSize")


class FeedbackUpdateRequest(ApiModel):
    status: FeedbackStatus | None = None
    operator_note: str | None = Field(default=None, alias="operatorNote", max_length=2000)


class FeedbackDeletedResponse(ApiModel):
    deleted: bool
