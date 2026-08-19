"""In-memory mail capture for tests."""

from __future__ import annotations

from dataclasses import dataclass

from mail.templates import EmailMessage


@dataclass
class CapturedEmail:
    to_email: str
    message: EmailMessage


_captured: list[CapturedEmail] = []


def capture_email(*, to_email: str, message: EmailMessage) -> None:
    _captured.append(CapturedEmail(to_email=to_email, message=message))


def get_captured_emails() -> list[CapturedEmail]:
    return list(_captured)


def clear_captured_emails() -> None:
    _captured.clear()
