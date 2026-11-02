"""Outbound mail transport: Resend HTTP API and/or SMTP.

Resend (HTTPS) works on every Railway plan. Plain SMTP is blocked on the Free,
Trial and Hobby plans and allowed from Pro up, so both stay available:

* ``MAIL_TRANSPORT=auto`` (default): Resend when ``RESEND_API_KEY`` is set,
  otherwise SMTP (local dev/test against Mailpit). Same behaviour as before.
* ``MAIL_TRANSPORT=resend`` / ``smtp``: force one of the two.
* ``MAIL_FALLBACK_TO_SMTP=true``: if a Resend send fails (e.g. the sandbox
  refuses a recipient) and a real SMTP server is configured, retry over SMTP.

SMTP supports STARTTLS (``SMTP_USE_TLS``, port 587) and implicit TLS
(``SMTP_USE_SSL``, port 465), always with certificate verification.
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid, parseaddr

import httpx

from config.settings.mail import MailSettingsMixin
from mail.templates import EmailMessage
from observability.logging import get_logger

logger = get_logger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"

# Server locali di sviluppo dove le credenziali in chiaro non escono dalla macchina/rete interna.
_LOCAL_SMTP_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "mailpit"})


class MailConfigError(Exception):
    """Configurazione email incoerente: l'invio non viene nemmeno tentato."""


def send_email(
    settings: MailSettingsMixin,
    *,
    to_email: str,
    message: EmailMessage,
) -> None:
    transport = settings.resolved_mail_transport()
    api_key = settings.resolved_resend_api_key()
    used = _deliver(settings, transport=transport, api_key=api_key, to_email=to_email, message=message)
    # Solo il canale usato: mai destinatario, oggetto o credenziali nei log.
    logger.info("mail_sent", extra={"via": used})


def _deliver(
    settings: MailSettingsMixin,
    *,
    transport: str,
    api_key: str | None,
    to_email: str,
    message: EmailMessage,
) -> str:
    if transport == "smtp":
        _send_via_smtp(settings, to_email=to_email, message=message)
        return "smtp"
    if transport == "resend" and not api_key:
        raise MailConfigError("MAIL_TRANSPORT=resend ma RESEND_API_KEY non è impostata.")
    if not api_key:  # auto senza chiave Resend
        _send_via_smtp(settings, to_email=to_email, message=message)
        return "smtp"

    try:
        _send_via_resend(settings, api_key=api_key, to_email=to_email, message=message)
        return "resend"
    except (httpx.HTTPError, OSError) as exc:
        if not (settings.resolved_flag("mail_fallback_to_smtp") and settings.is_smtp_configured()):
            raise
        # Nessun dato sensibile nel log: solo il tipo di errore, non destinatario né chiave.
        logger.warning("mail_resend_failed_fallback_to_smtp", extra={"error": type(exc).__name__})
        _send_via_smtp(settings, to_email=to_email, message=message)
        return "smtp"


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


def validate_smtp_settings(settings: MailSettingsMixin) -> None:
    """Rifiuta combinazioni insicure o contraddittorie prima di aprire la connessione."""
    use_tls = settings.resolved_flag("smtp_use_tls")
    use_ssl = settings.resolved_flag("smtp_use_ssl")
    if use_tls and use_ssl:
        raise MailConfigError(
            "SMTP_USE_TLS (STARTTLS, porta 587) e SMTP_USE_SSL (TLS implicito, porta 465) "
            "sono alternativi: impostane uno solo."
        )
    password = settings.resolved_smtp_password()
    host = (settings.smtp_host or "").strip().lower()
    if settings.smtp_user and password and not (use_tls or use_ssl) and host not in _LOCAL_SMTP_HOSTS:
        raise MailConfigError(
            "Credenziali SMTP su una connessione non cifrata: imposta SMTP_USE_TLS=true "
            "(porta 587) oppure SMTP_USE_SSL=true (porta 465)."
        )


def build_mime_message(
    settings: MailSettingsMixin,
    *,
    to_email: str,
    message: EmailMessage,
) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = message.subject
    # formataddr codifica solo il nome visualizzato (es. «FantApperò»): con una stringa
    # unica il nome accentato farebbe codificare anche l'indirizzo e il From resterebbe senza mittente.
    msg["From"] = formataddr((settings.mail_from_name, settings.mail_from), charset="utf-8")
    msg["To"] = to_email
    # Senza Date e Message-ID molti filtri antispam scartano o declassano il messaggio.
    msg["Date"] = formatdate(localtime=False)
    sender_domain = parseaddr(settings.mail_from)[1].rpartition("@")[2] or None
    msg["Message-ID"] = make_msgid(domain=sender_domain)
    msg.attach(MIMEText(message.text_body, "plain", "utf-8"))
    msg.attach(MIMEText(message.html_body, "html", "utf-8"))
    return msg


def _send_via_smtp(
    settings: MailSettingsMixin,
    *,
    to_email: str,
    message: EmailMessage,
) -> None:
    validate_smtp_settings(settings)
    msg = build_mime_message(settings, to_email=to_email, message=message)
    password = settings.resolved_smtp_password()
    timeout = settings.resolved_smtp_timeout()
    envelope_from = parseaddr(settings.mail_from)[1] or settings.mail_from

    if settings.resolved_flag("smtp_use_ssl"):
        client = smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)

    with client as smtp:
        if settings.resolved_flag("smtp_use_tls"):
            # Contesto esplicito: senza, starttls() non verificherebbe il certificato del server.
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_user and password:
            smtp.login(settings.smtp_user, password)
        smtp.sendmail(envelope_from, [to_email], msg.as_string())
