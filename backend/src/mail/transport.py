"""SMTP transport for outbound mail."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config.settings.mail import MailSettingsMixin
from mail.templates import EmailMessage


def send_email(
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
