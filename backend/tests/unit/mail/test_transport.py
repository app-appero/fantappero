"""Unit tests for the Resend/SMTP transport branch (mail.transport)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydantic import SecretStr

from config.settings.mail import MailSettingsMixin
from mail.templates import EmailMessage
from mail.transport import send_email


class _Settings(MailSettingsMixin):
    def __init__(self, *, resend_api_key: str | None = None) -> None:
        self.smtp_host = "mailpit"
        self.smtp_port = 1025
        self.smtp_user = None
        self.smtp_password = None
        self.smtp_use_tls = False
        self.resend_api_key = SecretStr(resend_api_key) if resend_api_key else None
        self.mail_from = "noreply@fantappero.local"
        self.mail_from_name = "FantApperò"


_MESSAGE = EmailMessage(subject="Ciao", text_body="testo", html_body="<p>testo</p>")


def test_send_email_uses_resend_http_api_when_key_is_set() -> None:
    settings = _Settings(resend_api_key="re_test_key")  # noqa: S106 - test fixture, not a real secret
    with patch("mail.transport.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        send_email(settings, to_email="tester@example.com", message=_MESSAGE)

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer re_test_key"
    assert kwargs["json"]["to"] == ["tester@example.com"]
    assert kwargs["json"]["subject"] == "Ciao"
    assert kwargs["json"]["from"] == "FantApperò <noreply@fantappero.local>"


def test_send_email_falls_back_to_smtp_when_no_resend_key() -> None:
    settings = _Settings(resend_api_key=None)
    with (
        patch("mail.transport.httpx.post") as mock_post,
        patch("mail.transport.smtplib.SMTP") as mock_smtp_cls,
    ):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp
        send_email(settings, to_email="tester@example.com", message=_MESSAGE)

    mock_post.assert_not_called()
    mock_smtp_cls.assert_called_once_with("mailpit", 1025, timeout=30)
    mock_smtp.sendmail.assert_called_once()
