"""Outbound mail transport: Resend HTTP API, or SMTP as fallback.

Many cloud platforms (Railway included) block outbound SMTP ports to fight
spam, so a plain smtplib send times out there even with correct credentials.
When RESEND_API_KEY is set, send over HTTPS instead; otherwise keep the
SMTP path for local dev/test against Mailpit.
"""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

from config.settings.mail import MailSettingsMixin
from mail.templates import EmailMessage

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(
    settings: MailSettingsMixin,
    *,
    to_email: str,
    message: EmailMessage,
) -> None:
    api_key = settings.resolved_resend_api_key()
    if api_key:
        _send_via_resend(settings, api_key=api_key, to_email=to_email, message=message)
    else:
        _send_via_smtp(settings, to_email=to_email, message=message)


def _send_via_resend(
    settings: MailSettingsMixin,
    *,
    api_key: str,
    to_email: str,
    message: EmailMessage,
) -> None:
    response = httpx.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": f"{settings.mail_from_name} <{settings.mail_from}>",
            "to": [to_email],
            "subject": message.subject,
            "text": message.text_body,
            "html": message.html_body,
        },
        timeout=30,
    )
    response.raise_for_status()


def _send_via_smtp(
    settings: MailSettingsMixin,
    *,
    to_email: str,
    message: EmailMessage,
) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = message.subject
    msg["From"] = f"{settings.mail_from_name} <{settings.mail_from}>"
    msg["To"] = to_email
    msg.attach(MIMEText(message.text_body, "plain", "utf-8"))
    msg.attach(MIMEText(message.html_body, "html", "utf-8"))

    password = settings.resolved_smtp_password()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_user and password:
            smtp.login(settings.smtp_user, password)
        smtp.sendmail(settings.mail_from, [to_email], msg.as_string())
