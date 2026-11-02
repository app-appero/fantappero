"""Diagnosi della configurazione SMTP, senza inviare nessuna email.

Uso (dal servizio `worker` su Railway, dove la porta può essere bloccata)::

    python -m mail.diagnostics               # controlla DNS, connessione, cifratura, login
    python -m mail.diagnostics --send-to me@example.com   # invia anche una email di prova

Non stampa mai la password né la chiave Resend.
"""

from __future__ import annotations

import argparse
import smtplib
import socket
import ssl
import sys
from dataclasses import dataclass

from config.settings.mail import MailSettingsMixin
from mail.templates import EmailMessage
from mail.transport import MailConfigError, send_email, validate_smtp_settings

RAILWAY_HINT = (
    "Su Railway l'SMTP in uscita è bloccato sui piani Free, Trial e Hobby e consentito dal Pro in su: "
    "dopo l'upgrade rifai il deploy del servizio. Se sei già sul Pro, controlla che il provider "
    "SMTP non blocchi gli IP di Railway."
)


@dataclass(frozen=True)
class CheckStep:
    name: str
    ok: bool
    detail: str


def _blocked_hint(exc: BaseException) -> str:
    if isinstance(exc, (TimeoutError, socket.timeout, ConnectionRefusedError, OSError)) and not isinstance(
        exc, ssl.SSLError
    ):
        return f" {RAILWAY_HINT}"
    return ""


def check_smtp(settings: MailSettingsMixin) -> list[CheckStep]:
    """Esegue i controlli in ordine e si ferma al primo che fallisce."""
    steps: list[CheckStep] = []

    def done(name: str, ok: bool, detail: str) -> bool:
        steps.append(CheckStep(name, ok, detail))
        return ok

    host = settings.smtp_host
    port = settings.smtp_port
    use_ssl = settings.resolved_flag("smtp_use_ssl")
    use_tls = settings.resolved_flag("smtp_use_tls")
    mode = "TLS implicito" if use_ssl else "STARTTLS" if use_tls else "nessuna cifratura"

    try:
        validate_smtp_settings(settings)
    except MailConfigError as exc:
        done("configurazione", False, str(exc))
        return steps
    done("configurazione", True, f"{host}:{port}, {mode}, mittente {settings.mail_from}")

    try:
        socket.getaddrinfo(host, port)
    except OSError as exc:
        done("risoluzione DNS", False, f"{host} non si risolve: {exc}")
        return steps
    done("risoluzione DNS", True, host)

    timeout = settings.resolved_smtp_timeout()
    try:
        client = (
            smtplib.SMTP_SSL(host, port, timeout=timeout, context=ssl.create_default_context())
            if use_ssl
            else smtplib.SMTP(host, port, timeout=timeout)
        )
    except ssl.SSLError as exc:
        done("connessione", False, f"errore TLS: {exc}")
        return steps
    except (OSError, smtplib.SMTPException) as exc:
        done("connessione", False, f"{type(exc).__name__}: {exc}.{_blocked_hint(exc)}")
        return steps
    done("connessione", True, "porta raggiungibile")

    with client as smtp:
        if use_tls:
            try:
                smtp.starttls(context=ssl.create_default_context())
            except (ssl.SSLError, smtplib.SMTPException, OSError) as exc:
                done("cifratura", False, f"STARTTLS non riuscito: {exc}")
                return steps
            done("cifratura", True, "STARTTLS con certificato verificato")
        password = settings.resolved_smtp_password()
        if settings.smtp_user and password:
            try:
                smtp.login(settings.smtp_user, password)
            except smtplib.SMTPAuthenticationError as exc:
                done("login", False, f"credenziali rifiutate ({exc.smtp_code})")
                return steps
            except (smtplib.SMTPException, OSError) as exc:
                done("login", False, f"{type(exc).__name__}: {exc}")
                return steps
            done("login", True, f"autenticato come {settings.smtp_user}")
        else:
            done("login", True, "nessuna credenziale configurata (server senza autenticazione)")
        try:
            code, _ = smtp.noop()
        except (smtplib.SMTPException, OSError) as exc:
            done("NOOP", False, f"{type(exc).__name__}: {exc}")
            return steps
        done("NOOP", code == 250, f"risposta {code}")
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnosi della configurazione email (SMTP).")
    parser.add_argument("--send-to", help="invia anche una email di prova a questo indirizzo")
    args = parser.parse_args(argv)

    from config.settings.loader import get_worker_settings

    settings = get_worker_settings()
    print(f"Trasporto: {settings.resolved_mail_transport()} · fallback SMTP: "
          f"{'sì' if settings.resolved_flag('mail_fallback_to_smtp') else 'no'} · "
          f"Resend: {'configurato' if settings.resolved_resend_api_key() else 'non configurato'}")
    failed = False
    for step in check_smtp(settings):
        print(f"[{'OK' if step.ok else 'ERRORE'}] {step.name}: {step.detail}")
        failed = failed or not step.ok
    if failed:
        return 1
    if args.send_to:
        send_email(
            settings,
            to_email=args.send_to,
            message=EmailMessage(
                subject="Prova invio FantApperò",
                text_body="Se leggi questo messaggio la configurazione email funziona.",
                html_body="<p>Se leggi questo messaggio la configurazione email funziona.</p>",
            ),
        )
        print(f"[OK] email di prova inviata a {args.send_to}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
