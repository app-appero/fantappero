"""SMTP come alternativa a Resend: scelta del trasporto, TLS, intestazioni e diagnosi."""

from __future__ import annotations

import smtplib
import ssl
from unittest.mock import MagicMock, patch

import httpx
import pytest
from pydantic import SecretStr

from config.settings.mail import MailSettingsMixin
from mail import diagnostics
from mail.templates import EmailMessage
from mail.transport import MailConfigError, build_mime_message, send_email

MESSAGE = EmailMessage(subject="Ciao", text_body="testo", html_body="<p>testo</p>")


class Settings(MailSettingsMixin):
    def __init__(self, **overrides) -> None:
        values = {
            "smtp_host": "smtp.provider.example",
            "smtp_port": 587,
            "smtp_user": "mailer@fantappero.example",
            "smtp_password": SecretStr("s3cret"),
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
            "smtp_timeout_seconds": 20,
            "resend_api_key": None,
            "mail_transport": "auto",
            "mail_fallback_to_smtp": False,
            "mail_from": "mailer@fantappero.example",
            "mail_from_name": "FantApperò",
        }
        values.update(overrides)
        for key, value in values.items():
            setattr(self, key, value)


def _fake_smtp():
    client = MagicMock()
    client.__enter__.return_value = client
    return client


# --- scelta del trasporto ---------------------------------------------------------------


def test_auto_uses_resend_when_the_key_is_set_even_if_smtp_is_configured():
    settings = Settings(resend_api_key=SecretStr("re_key"))
    with patch("mail.transport.httpx.post") as post, patch("mail.transport.smtplib.SMTP") as smtp:
        send_email(settings, to_email="a@example.com", message=MESSAGE)
    post.assert_called_once()
    smtp.assert_not_called()


def test_smtp_transport_ignores_the_resend_key():
    settings = Settings(resend_api_key=SecretStr("re_key"), mail_transport="smtp")
    client = _fake_smtp()
    with patch("mail.transport.httpx.post") as post, patch("mail.transport.smtplib.SMTP", return_value=client):
        send_email(settings, to_email="a@example.com", message=MESSAGE)
    post.assert_not_called()
    client.sendmail.assert_called_once()


def test_resend_transport_without_a_key_is_a_configuration_error():
    with pytest.raises(MailConfigError, match="RESEND_API_KEY"):
        send_email(Settings(mail_transport="resend"), to_email="a@example.com", message=MESSAGE)


def test_unknown_transport_value_behaves_like_auto():
    assert Settings(mail_transport="boh").resolved_mail_transport() == "auto"
    assert Settings(mail_transport=" SMTP ").resolved_mail_transport() == "smtp"


# --- fallback da Resend a SMTP ----------------------------------------------------------------


def _resend_refuses():
    response = MagicMock(status_code=403)
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=MagicMock(), response=response
    )
    return response


def test_fallback_delivers_over_smtp_when_resend_refuses_the_recipient():
    settings = Settings(resend_api_key=SecretStr("re_key"), mail_fallback_to_smtp=True)
    client = _fake_smtp()
    with (
        patch("mail.transport.httpx.post", return_value=_resend_refuses()),
        patch("mail.transport.smtplib.SMTP", return_value=client),
    ):
        send_email(settings, to_email="other@example.com", message=MESSAGE)
    client.sendmail.assert_called_once()


def test_without_the_fallback_flag_a_resend_failure_is_raised():
    settings = Settings(resend_api_key=SecretStr("re_key"), mail_fallback_to_smtp=False)
    with (
        patch("mail.transport.httpx.post", return_value=_resend_refuses()),
        patch("mail.transport.smtplib.SMTP") as smtp,
        pytest.raises(httpx.HTTPStatusError),
    ):
        send_email(settings, to_email="other@example.com", message=MESSAGE)
    smtp.assert_not_called()


def test_fallback_needs_a_real_smtp_server():
    settings = Settings(
        resend_api_key=SecretStr("re_key"),
        mail_fallback_to_smtp=True,
        smtp_host="localhost",
        smtp_user=None,
        smtp_password=None,
    )
    with (
        patch("mail.transport.httpx.post", return_value=_resend_refuses()),
        pytest.raises(httpx.HTTPStatusError),
    ):
        send_email(settings, to_email="other@example.com", message=MESSAGE)


# --- TLS e credenziali ------------------------------------------------------------------------------


def test_starttls_verifies_the_server_certificate_and_logs_in():
    client = _fake_smtp()
    with patch("mail.transport.smtplib.SMTP", return_value=client):
        send_email(Settings(), to_email="a@example.com", message=MESSAGE)
    (context,) = [call.kwargs["context"] for call in client.starttls.call_args_list]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname is True
    client.login.assert_called_once_with("mailer@fantappero.example", "s3cret")
    assert client.sendmail.call_args.args[0] == "mailer@fantappero.example"


def test_implicit_ssl_uses_smtp_ssl_with_a_verifying_context():
    settings = Settings(smtp_port=465, smtp_use_tls=False, smtp_use_ssl=True)
    client = _fake_smtp()
    with (
        patch("mail.transport.smtplib.SMTP_SSL", return_value=client) as ssl_cls,
        patch("mail.transport.smtplib.SMTP") as plain,
    ):
        send_email(settings, to_email="a@example.com", message=MESSAGE)
    plain.assert_not_called()
    kwargs = ssl_cls.call_args.kwargs
    assert ssl_cls.call_args.args == ("smtp.provider.example", 465)
    assert kwargs["context"].verify_mode == ssl.CERT_REQUIRED and kwargs["timeout"] == 20
    client.starttls.assert_not_called()
    client.login.assert_called_once()


def test_tls_and_ssl_together_are_rejected():
    with pytest.raises(MailConfigError, match="alternativi"):
        send_email(Settings(smtp_use_ssl=True), to_email="a@example.com", message=MESSAGE)


def test_credentials_are_never_sent_over_an_unencrypted_remote_connection():
    settings = Settings(smtp_use_tls=False, smtp_use_ssl=False)
    with patch("mail.transport.smtplib.SMTP") as smtp, pytest.raises(MailConfigError, match="non cifrata"):
        send_email(settings, to_email="a@example.com", message=MESSAGE)
    smtp.assert_not_called()


def test_plain_smtp_without_credentials_is_fine_for_local_mailpit():
    settings = Settings(
        smtp_host="mailpit", smtp_port=1025, smtp_user=None, smtp_password=None, smtp_use_tls=False
    )
    client = _fake_smtp()
    with patch("mail.transport.smtplib.SMTP", return_value=client):
        send_email(settings, to_email="a@example.com", message=MESSAGE)
    client.starttls.assert_not_called()
    client.login.assert_not_called()


# --- intestazioni ---------------------------------------------------------------------------------------


def test_message_has_date_and_message_id_from_the_sender_domain():
    mime = build_mime_message(Settings(), to_email="a@example.com", message=MESSAGE)
    assert mime["Date"]
    assert mime["Message-ID"].endswith("@fantappero.example>")
    assert mime["To"] == "a@example.com"


def test_accented_sender_name_keeps_the_address_a_real_mailbox():
    """Con un nome accentato il From deve restare «nome + indirizzo», non un unico nome codificato."""
    from email import message_from_string
    from email.header import decode_header, make_header
    from email.utils import parseaddr

    mime = build_mime_message(Settings(), to_email="a@example.com", message=MESSAGE)
    received = message_from_string(mime.as_string())
    name, address = parseaddr(received["From"])
    assert address == "mailer@fantappero.example"
    assert str(make_header(decode_header(name))) == "FantApperò"


# --- diagnosi ---------------------------------------------------------------------------------------------


def test_diagnostics_reports_every_step_without_sending_mail():
    client = _fake_smtp()
    client.noop.return_value = (250, b"OK")
    with (
        patch("mail.diagnostics.socket.getaddrinfo"),
        patch("mail.diagnostics.smtplib.SMTP", return_value=client),
    ):
        steps = diagnostics.check_smtp(Settings())
    assert [step.name for step in steps] == ["configurazione", "risoluzione DNS", "connessione", "cifratura", "login", "NOOP"]
    assert all(step.ok for step in steps)
    client.sendmail.assert_not_called()
    assert "s3cret" not in " ".join(step.detail for step in steps)


def test_diagnostics_explains_a_blocked_port_with_the_railway_hint():
    with (
        patch("mail.diagnostics.socket.getaddrinfo"),
        patch("mail.diagnostics.smtplib.SMTP", side_effect=TimeoutError("timed out")),
    ):
        steps = diagnostics.check_smtp(Settings())
    last = steps[-1]
    assert (last.name, last.ok) == ("connessione", False)
    assert "Pro" in last.detail and "deploy" in last.detail


def test_diagnostics_reports_rejected_credentials_without_leaking_them():
    client = _fake_smtp()
    client.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with (
        patch("mail.diagnostics.socket.getaddrinfo"),
        patch("mail.diagnostics.smtplib.SMTP", return_value=client),
    ):
        steps = diagnostics.check_smtp(Settings())
    assert (steps[-1].name, steps[-1].ok) == ("login", False)
    assert "535" in steps[-1].detail and "s3cret" not in steps[-1].detail


def test_diagnostics_stops_on_a_bad_configuration():
    steps = diagnostics.check_smtp(Settings(smtp_use_ssl=True))
    assert [(s.name, s.ok) for s in steps] == [("configurazione", False)]
