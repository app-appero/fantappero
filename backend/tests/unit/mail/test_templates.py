"""Mail template unit tests."""

from __future__ import annotations

from mail.templates import build_email_verification_message, build_password_reset_message


def test_email_verification_template_italian_links() -> None:
    message = build_email_verification_message(
        verify_url="http://localhost:5173/accedi/verifica?token=abc",
        display_name="Marco",
    )
    assert "Verifica" in message.subject
    assert "Marco" in message.text_body
    assert "http://localhost:5173/accedi/verifica?token=abc" in message.html_body


def test_password_reset_template_italian_links() -> None:
    message = build_password_reset_message(
        reset_url="http://localhost:5173/accedi/reimposta-password?token=xyz",
        display_name="Luca",
    )
    assert "password" in message.subject.lower()
    assert "Luca" in message.text_body
    assert "reimposta-password?token=xyz" in message.html_body
