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


class CannotImpersonateSelfError(AdminError):
    def __init__(self) -> None:
        super().__init__("Non puoi impersonare te stesso.", code="cannot_impersonate_self")


class AdminTransferNotFoundError(AdminError):
    def __init__(self) -> None:
        super().__init__("Trasferimento non trovato.", code="admin_transfer_not_found")


class AdminTransferAlreadyReviewedError(AdminError):
    def __init__(self) -> None:
        super().__init__(
            "Questo trasferimento è già stato revisionato.",
            code="admin_transfer_already_reviewed",
        )


class ProtectedOperatorError(AdminError):
    def __init__(self) -> None:
        super().__init__(
            "Questo operatore è protetto: non può essere declassato, eliminato o bloccato.",
            code="protected_operator",
        )


class CannotModifyOperatorError(AdminError):
    def __init__(self) -> None:
        super().__init__(
            "Per eliminare o bloccare un operatore revoca prima il suo ruolo.",
            code="operator_must_be_revoked_first",
        )


class CannotDeleteSelfError(AdminError):
    def __init__(self) -> None:
        super().__init__("Non puoi eliminare te stesso.", code="cannot_delete_self")
