"""Celery tasks for outbound email."""

from __future__ import annotations

import os

from app.worker import celery_app
from config.settings.loader import get_worker_settings
from mail.capture import capture_email
from mail.templates import EmailMessage
from mail.transport import send_email
from observability.metrics import get_metrics


@celery_app.task(name="mail.send_message")
def send_message_task(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
    template: str,
) -> None:
    message = EmailMessage(subject=subject, text_body=text_body, html_body=html_body)
    if os.environ.get("FANTAPPERO_ENV", "").lower() == "test":
        capture_email(to_email=to_email, message=message)
        get_metrics().incr("auth_email_sent_total", labels={"template": template})
        return

    settings = get_worker_settings()
    send_email(settings, to_email=to_email, message=message)
    get_metrics().incr("auth_email_sent_total", labels={"template": template})
