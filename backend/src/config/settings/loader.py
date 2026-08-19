"""Load, validate, and cache settings with redacted error messages."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import ValidationError

from config.settings.api import ApiSettings
from config.settings.redaction import redact_secrets, redact_value
from config.settings.worker import WorkerSettings


class ConfigurationError(RuntimeError):
    """Raised when mandatory configuration is missing or invalid."""

    def __init__(self, message: str, *, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(redact_secrets(message))
        self.errors = redact_value(errors or [])


def _format_validation_error(exc: ValidationError) -> ConfigurationError:
    messages: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()))
        msg = err.get("msg", "invalid value")
        if loc:
            messages.append(f"{loc}: {msg}")
        else:
            messages.append(str(msg))
    body = "Configuration validation failed:\n- " + "\n- ".join(messages)
    return ConfigurationError(body, errors=list(exc.errors()))


@lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    try:
        return ApiSettings()
    except ValidationError as exc:
        raise _format_validation_error(exc) from None


@lru_cache(maxsize=1)
def get_worker_settings() -> WorkerSettings:
    try:
        return WorkerSettings()
    except ValidationError as exc:
        raise _format_validation_error(exc) from None


def validate_api_settings() -> ApiSettings:
    """Fail fast at process startup with a redacted, human-readable message."""
    return get_api_settings()


def validate_worker_settings() -> WorkerSettings:
    """Fail fast at worker startup with a redacted, human-readable message."""
    return get_worker_settings()


def reset_settings_cache() -> None:
    """Clear cached settings (for tests)."""
    get_api_settings.cache_clear()
    get_worker_settings.cache_clear()
