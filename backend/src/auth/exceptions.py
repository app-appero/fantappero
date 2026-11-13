"""Auth domain exceptions."""

from __future__ import annotations


class AuthError(Exception):
    """Base auth error with user-facing Italian message."""

    def __init__(self, message: str, *, code: str = "auth_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class InvalidCredentialsError(AuthError):
    def __init__(self, message: str = "Email o password non validi.") -> None:
        super().__init__(message, code="invalid_credentials")


class SessionRequiredError(InvalidCredentialsError):
    """Richiesta autenticata senza token valido (stesso codice, messaggio chiaro)."""

    def __init__(self) -> None:
        super().__init__("Accesso richiesto: sessione mancante o scaduta.")


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


class GoogleAuthError(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "Accesso con Google non riuscito. Riprova.",
            code="google_auth_failed",
        )


class MobileHandoffExpiredError(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "Il collegamento con l'app è scaduto. Torna all'app e riprova.",
            code="mobile_handoff_expired",
        )


class TesterOnlyError(AuthError):
    """Modalità test attiva: l'account non è tra i tester autorizzati."""

    def __init__(self) -> None:
        super().__init__(
            "Non autorizzato: l'accesso è riservato ai tester del pilota.",
            code="tester_only",
        )


class AccountBlockedError(AuthError):
    """L'indirizzo è in lista nera: nessun accesso e nessuna nuova registrazione."""

    def __init__(self) -> None:
        super().__init__(
            "Accesso non consentito: questo account è stato bloccato.",
            code="account_blocked",
        )


class RateLimitExceededError(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "Troppi tentativi. Riprova tra qualche minuto.",
            code="rate_limit_exceeded",
        )


class ValidationAuthError(AuthError):
    pass
