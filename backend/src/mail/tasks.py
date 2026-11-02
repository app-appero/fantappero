"""Celery tasks for outbound email."""

from __future__ import annotations

import os

from app.worker import celery_app
from config.settings.loader import get_worker_settings
from mail.capture import capture_email
from mail.templates import EmailMessage
from mail.transport import send_email
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)


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
    try:
        send_email(settings, to_email=to_email, message=message)
    except Exception as exc:
        # L'invio è asincrono: il pannello non vede l'errore, quindi va scritto chiaro nei log
        # del worker (canale configurato e tipo di errore; mai destinatario, testo o credenziali).
        details = {
            "template": template,
            "transport": settings.resolved_mail_transport(),
            "resend_configured": bool(settings.resolved_resend_api_key()),
            "smtp_host": settings.smtp_host,
            "error": type(exc).__name__,
            # Fase SMTP in cui è fallito (connessione/starttls/login/invio) e codice di risposta,
            # se il server ne ha dato uno. Mai il testo della risposta: può contenere indirizzi.
            "stage": getattr(exc, "mail_stage", None),
            "smtp_code": getattr(exc, "smtp_code", None),
        }
        # I campi stanno anche nel testo: il worker stampa solo il messaggio (formato Celery),
        # non gli `extra` che il log JSON dell'API invece mostra.
        logger.error(
            "mail_send_failed " + " ".join(f"{key}={value}" for key, value in details.items()),
            extra=details,
        )
        get_metrics().incr("auth_email_failed_total", labels={"template": template})
        raise
    get_metrics().incr("auth_email_sent_total", labels={"template": template})
