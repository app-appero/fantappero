"""AI assistant domain exceptions (EP10)."""

from __future__ import annotations

from auth.exceptions import AuthError


class AiQuotaExceededError(AuthError):
    def __init__(self) -> None:
        super().__init__(
            "Hai raggiunto il limite giornaliero di richieste all'assistente. Riprova domani.",
            code="ai_quota_exceeded",
        )


class AiInteractionNotFoundError(AuthError):
    def __init__(self) -> None:
        super().__init__("Interazione non trovata.", code="ai_interaction_not_found")
