"""HTTP schemas for entitlements and the subscription webhook (EP11-01/02)."""

from __future__ import annotations

from pydantic import Field

from auth.schemas import ApiModel


class EntitlementStatusResponse(ApiModel):
    plan: str
    active_until: str | None = Field(default=None, alias="activeUntil")
    ai_daily_limit: int = Field(alias="aiDailyLimit")


class SubscriptionWebhookRequest(ApiModel):
    event_id: str = Field(alias="eventId", min_length=1)
    user_id: str = Field(alias="userId")
    plan_code: str = Field(alias="planCode")


class SubscriptionWebhookResponse(ApiModel):
    payment_id: str = Field(alias="paymentId")
    plan_code: str = Field(alias="planCode")
    processed: bool
