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


class AdminTransferNotFoundError(AdminError):
    def __init__(self) -> None:
        super().__init__("Trasferimento non trovato.", code="admin_transfer_not_found")


class AdminTransferAlreadyReviewedError(AdminError):
    def __init__(self) -> None:
        super().__init__(
            "Questo trasferimento è già stato revisionato.",
            code="admin_transfer_already_reviewed",
        )
