"""Redact secrets from strings and structured data before logging or serialization."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_REDACTED = "***REDACTED***"

# Credential segments in URLs (user:password@host).
_DSN_CREDENTIALS = re.compile(
    r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*://)"
    r"(?P<creds>[^/@\s]+(?::[^/@\s]+)?@)",
    re.ASCII,
)

# Key/value patterns commonly holding secrets.
_KV_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)(\S+)"),
    re.compile(r"(?i)(bearer\s+)(\S+)"),
    re.compile(
        r"(?i)(api[_-]?football[_-]?key|apisports[_-]?key|x-apisports-key|"
        r"x-rapidapi-key|token|secret|password|passwd|api[_-]?key)\s*[:=]\s*"
        r"['\"]?(\S+)['\"]?"
    ),
)

# Standalone high-entropy tokens (20+ alnum) after sensitive key names in JSON-ish text.
_JSON_SECRET = re.compile(
    r'(?i)("(?:api[_-]?key|token|secret|password|authorization)"\s*:\s*")([^"]+)(")'
)


def redact_dsn(value: str) -> str:
    """Mask credentials embedded in connection URLs."""

    def _replace(match: re.Match[str]) -> str:
        scheme = match.group("scheme")
        creds = match.group("creds")
        if "@" not in creds:
            return match.group(0)
        user_part, _, host_part = creds.partition("@")
        if ":" in user_part:
            user, _password = user_part.split(":", 1)
            masked = f"{user}:{_REDACTED}@{host_part}"
        else:
            masked = f"{user_part}:{_REDACTED}@{host_part}"
        return f"{scheme}{masked}"

    return _DSN_CREDENTIALS.sub(_replace, value)


def redact_url_password(url: str) -> str:
    """Mask password component using stdlib URL parsing."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return redact_dsn(url)
    if not parts.password:
        return redact_dsn(url)
    netloc = parts.netloc.replace(f":{parts.password}@", f":{_REDACTED}@")
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def redact_value(value: Any) -> Any:
    """Recursively redact secrets from a value suitable for logs or error payloads."""
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list | tuple):
        redacted = [redact_value(item) for item in value]
        return type(value)(redacted) if isinstance(value, tuple) else redacted
    if isinstance(value, set):
        return {redact_value(item) for item in value}
    return value


def _redact_kv_match(match: re.Match[str]) -> str:
    full = match.group(0)
    if match.lastindex is None or match.lastindex < 2:
        return _REDACTED
    secret = match.group(match.lastindex)
    return full.replace(secret, _REDACTED)


def redact_string(text: str) -> str:
    if not text:
        return text
    result = redact_url_password(text)
    result = redact_dsn(result)
    for pattern in _KV_PATTERNS:
        result = pattern.sub(_redact_kv_match, result)
    result = _JSON_SECRET.sub(rf"\1{_REDACTED}\3", result)
    return result


def redact_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    sensitive_keys = {
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "api_football_key",
        "apisports_key",
        "authorization",
        "database_url",
        "redis_url",
        "celery_broker_url",
        "celery_result_backend",
        "dsn",
    }
    out: dict[str, Any] = {}
    for key, val in data.items():
        normalized = key.lower().replace("-", "_")
        if normalized in sensitive_keys or any(
            part in normalized for part in ("password", "secret", "token", "api_key")
        ):
            out[key] = _REDACTED if val else val
        else:
            out[key] = redact_value(val)
    return out


def redact_secrets(text: str) -> str:
    """Alias for string redaction (used in tests and log formatters)."""
    return redact_string(text)
