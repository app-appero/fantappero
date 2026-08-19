"""Authorization domain exceptions (EP02-03)."""

from __future__ import annotations


class AuthorizationError(Exception):
    """Base authorization error with user-facing Italian message."""

    def __init__(self, message: str, *, code: str = "forbidden") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ForbiddenError(AuthorizationError):
    """Caller lacks the required permission."""

    def __init__(self) -> None:
        super().__init__(
            "Non hai i permessi per eseguire questa operazione.",
            code="forbidden",
        )


class LeagueAccessDeniedError(AuthorizationError):
    """Caller is authenticated but not allowed in the target league tenant."""

    def __init__(self) -> None:
        super().__init__(
            "Non hai accesso a questa lega.",
            code="league_access_denied",
        )


class LeagueNotFoundError(AuthorizationError):
    """Target league does not exist."""

    def __init__(self) -> None:
        super().__init__(
            "Lega non trovata.",
            code="league_not_found",
        )
