"""Secret redaction for logs and serialized errors."""

from __future__ import annotations

from config.settings.redaction import redact_mapping, redact_secrets, redact_value


def test_redact_postgresql_dsn_password() -> None:
    dsn = "postgresql://fantappero:my_secret_password@postgres:5432/fantappero"
    redacted = redact_secrets(dsn)
    assert "my_secret_password" not in redacted
    assert "fantappero" in redacted
    assert "***REDACTED***" in redacted


def test_redact_redis_url_with_password() -> None:
    url = "redis://:redis_pass@127.0.0.1:6379/0"
    redacted = redact_secrets(url)
    assert "redis_pass" not in redacted


def test_redact_bearer_token() -> None:
    header = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload"
    redacted = redact_secrets(header)
    assert "eyJhbGci" not in redacted
    assert "Bearer" in redacted


def test_redact_api_key_assignment() -> None:
    line = "API_FOOTBALL_KEY=abc123def456ghi789jkl012"
    redacted = redact_secrets(line)
    assert "abc123def456ghi789jkl012" not in redacted
    assert "API_FOOTBALL_KEY" in redacted


def test_redact_mapping_masks_sensitive_keys() -> None:
    payload = {
        "database_url": "postgresql://u:pw@h/db",
        "status": "error",
        "nested": {"token": "tok_1234567890abcdef"},
    }
    redacted = redact_mapping(payload)
    assert redacted["database_url"] == "***REDACTED***"
    assert redacted["nested"]["token"] == "***REDACTED***"
    assert redacted["status"] == "error"


def test_redact_value_recurses_through_structures() -> None:
    data = {
        "errors": [
            "password= hunter2",
            '{"api_key": "aaaaaaaaaaaaaaaaaaaa"}',
        ]
    }
    redacted = redact_value(data)
    text = str(redacted)
    assert "hunter2" not in text
    assert "aaaaaaaaaaaaaaaaaaaa" not in text
