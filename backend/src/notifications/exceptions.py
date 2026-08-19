"""Notification domain exceptions (EP09-01)."""

from __future__ import annotations

from auth.exceptions import AuthError


class NotificationNotFoundError(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "Notifica non trovata.",
            code="notification_not_found",
        )
