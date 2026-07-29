"""Development email delivery (log-only until SMTP card)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def send_verification_email(*, email: str, token: str, base_url: str) -> None:
    link = f"{base_url.rstrip('/')}/verify-email?token={token}"
    logger.info(
        "auth.email verification queued",
        extra={"recipient": email, "action": "verify_email", "link": link},
    )


def send_password_reset_email(*, email: str, token: str, base_url: str) -> None:
    link = f"{base_url.rstrip('/')}/reset-password?token={token}"
    logger.info(
        "auth.email password_reset queued",
        extra={"recipient": email, "action": "password_reset", "link": link},
    )
