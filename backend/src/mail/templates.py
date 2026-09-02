"""Italian email templates for auth flows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    subject: str
    text_body: str
    html_body: str


def build_email_verification_message(*, verify_url: str, display_name: str) -> EmailMessage:
    subject = "Verifica il tuo account FantApperò"
    text_body = (
        f"Ciao {display_name},\n\n"
        "Grazie per esserti registrato su FantApperò.\n"
        f"Per attivare il tuo account, apri questo link:\n{verify_url}\n\n"
        "Se non ti sei registrato, ignora questo messaggio.\n"
    )
    html_body = (
        f"<p>Ciao {display_name},</p>"
        "<p>Grazie per esserti registrato su FantApperò.</p>"
        f'<p><a href="{verify_url}">Verifica il tuo account</a></p>'
        "<p>Se non ti sei registrato, ignora questo messaggio.</p>"
    )
    return EmailMessage(subject=subject, text_body=text_body, html_body=html_body)


def build_password_reset_message(*, reset_url: str, display_name: str) -> EmailMessage:
    subject = "Reimposta la password FantApperò"
    text_body = (
        f"Ciao {display_name},\n\n"
        "Hai richiesto di reimpostare la password.\n"
        f"Apri questo link per scegliere una nuova password:\n{reset_url}\n\n"
        "Se non hai richiesto il reset, ignora questo messaggio.\n"
    )
    html_body = (
        f"<p>Ciao {display_name},</p>"
        "<p>Hai richiesto di reimpostare la password.</p>"
        f'<p><a href="{reset_url}">Reimposta la password</a></p>'
        "<p>Se non hai richiesto il reset, ignora questo messaggio.</p>"
    )
    return EmailMessage(subject=subject, text_body=text_body, html_body=html_body)
