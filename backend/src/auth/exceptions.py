"""Auth domain exceptions."""

from __future__ import annotations


class AuthError(Exception):
    """Base auth error with user-facing Italian message."""

    def __init__(self, message: str, *, code: str = "auth_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class InvalidCredentialsError(AuthError):
    def __init__(self) -> None:
        super().__init__("Email o password non validi.", code="invalid_credentials")


class EmailNotVerifiedError(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "Verifica la tua email prima di accedere.",
            code="email_not_verified",
        )


class EmailAlreadyRegisteredError(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "Se l'indirizzo email è valido, riceverai un messaggio con le istruzioni.",
            code="email_already_registered",
        )


class InvalidTokenError(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "Il link non è valido o è scaduto. Richiedi un nuovo messaggio.",
            code="invalid_token",
        )


class RateLimitExceededError(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "Troppi tentativi. Riprova tra qualche minuto.",
            code="rate_limit_exceeded",
        )


class ValidationAuthError(AuthError):
    pass
