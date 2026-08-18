"""Admin panel domain exceptions (EP11-04a)."""

from __future__ import annotations


class AdminError(Exception):
    """Base admin error with user-facing Italian message."""

    def __init__(self, message: str, *, code: str = "admin_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class AdminUserNotFoundError(AdminError):
    def __init__(self) -> None:
        super().__init__("Utente non trovato.", code="admin_user_not_found")


class LastOperatorRevokeError(AdminError):
    def __init__(self) -> None:
        super().__init__(
            "Non puoi revocare l'ultimo operatore rimasto sulla piattaforma.",
            code="last_operator",
        )
