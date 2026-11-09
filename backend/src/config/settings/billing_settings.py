"""Subscription webhook settings (EP11-02)."""

from __future__ import annotations

from pydantic import Field

#: See ``AuthSettingsMixin.DEFAULT_JWT_SECRET`` — same reasoning, different header.
DEFAULT_BILLING_WEBHOOK_SECRET = "fantappero_local_billing_webhook_dev_only"


class BillingSettingsMixin:
    """Env knobs for the subscription payment webhook.

    No real payment provider is integrated (see billing/webhook_service.py);
    this is a shared-secret header check standing in for real provider
    signature verification (e.g. Stripe) until one is actually configured.
    """

    billing_webhook_secret: str = Field(
        default=DEFAULT_BILLING_WEBHOOK_SECRET,
        validation_alias="BILLING_WEBHOOK_SECRET",
        description="Shared secret checked against the X-Webhook-Secret header.",
    )
