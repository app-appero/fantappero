"""Log-oriented redaction for secrets and personal data (PII)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from config.settings.redaction import redact_mapping, redact_string, redact_value

_REDACTED = "***REDACTED***"

# Field names that must never appear in clear text in structured logs.
_PII_KEYS = frozenset(
    {
        "email",
        "e_mail",
        "mail",
        "phone",
        "telephone",
        "mobile",
        "cell",
        "fiscal_code",
        "codice_fiscale",
        "cf",
        "ssn",
        "tax_id",
        "date_of_birth",
        "dob",
        "birth_date",
        "address",
        "street",
        "iban",
        "credit_card",
        "card_number",
        "full_name",
        "first_name",
        "last_name",
        "surname",
    }
)


def _is_pii_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized in _PII_KEYS:
        return True
    return any(part in normalized for part in ("email", "phone", "iban", "fiscal", "ssn", "birth"))


def _mask_pii(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, val in value.items():
            if _is_pii_key(str(key)) and val not in (None, ""):
                out[key] = _REDACTED
            else:
                out[key] = _mask_pii(val)
        return out
    if isinstance(value, list):
        return [_mask_pii(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_mask_pii(item) for item in value)
    return value


def redact_log_value(value: Any) -> Any:
    """Redact secrets and PII from a value destined for logs."""
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, Mapping):
        return redact_log_mapping(value)
    if isinstance(value, list | tuple):
        redacted = [redact_log_value(item) for item in value]
        return type(value)(redacted) if isinstance(value, tuple) else redacted
    if isinstance(value, set):
        return {redact_log_value(item) for item in value}
    return redact_value(value)


def redact_log_mapping(data: Mapping[str, Any]) -> dict[str, Any]:
    """Apply secret redaction then mask PII field names."""
    return _mask_pii(redact_mapping(data))
