"""Typed errors for the API-Football adapter (never leak secrets)."""

from __future__ import annotations


class ProviderError(Exception):
    """Base error for Sport Data provider I/O."""

    def __init__(self, message: str, *, endpoint: str | None = None) -> None:
        self.endpoint = endpoint
        super().__init__(message)


class ProviderAuthError(ProviderError):
    """Missing or rejected provider credentials."""


class ProviderRateLimitError(ProviderError):
    """HTTP 429 or quota exhausted according to provider headers/body."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: str | None = None,
        retry_after_seconds: float | None = None,
        remaining: int | None = None,
    ) -> None:
        self.retry_after_seconds = retry_after_seconds
        self.remaining = remaining
        super().__init__(message, endpoint=endpoint)


class ProviderHttpError(ProviderError):
    """Non-success HTTP response from the provider."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: str | None = None,
        status_code: int | None = None,
    ) -> None:
        self.status_code = status_code
        super().__init__(message, endpoint=endpoint)


class ProviderResponseError(ProviderError):
    """Malformed envelope or provider-declared errors in the JSON body."""

    def __init__(
        self,
        message: str,
        *,
        endpoint: str | None = None,
        provider_errors: object | None = None,
    ) -> None:
        self.provider_errors = provider_errors
        super().__init__(message, endpoint=endpoint)


class ProviderConfigError(ProviderError):
    """Adapter misconfiguration (e.g. missing API key)."""
