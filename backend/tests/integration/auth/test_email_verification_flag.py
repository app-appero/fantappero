"""Dev: verifica email facoltativa (AUTH_EMAIL_VERIFICATION_REQUIRED=false)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from config.settings.loader import reset_settings_cache
from mail.capture import get_captured_emails

PASSWORD = "Password123!"


def _register(client: TestClient, email: str):
    return client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": "Utente Prova"},
    )


def _login(client: TestClient, email: str):
    return client.post("/auth/login", json={"email": email, "password": PASSWORD})


def test_verification_is_required_by_default(client: TestClient) -> None:
    assert _register(client, "verif.default@example.com").status_code == 201
    response = _login(client, "verif.default@example.com")
    assert response.status_code == 403
    assert response.json()["code"] == "email_not_verified"


def test_account_is_usable_right_away_when_verification_is_off(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTH_EMAIL_VERIFICATION_REQUIRED", "false")
    reset_settings_cache()
    emails_before = len(get_captured_emails())

    assert _register(client, "verif.spenta@example.com").status_code == 201

    assert len(get_captured_emails()) == emails_before
    response = _login(client, "verif.spenta@example.com")
    assert response.status_code == 200
    assert "accessToken" in response.json()


def test_an_already_registered_unverified_account_gets_verified_at_login_when_off(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _register(client, "verif.prima@example.com").status_code == 201
    assert _login(client, "verif.prima@example.com").status_code == 403

    monkeypatch.setenv("AUTH_EMAIL_VERIFICATION_REQUIRED", "false")
    reset_settings_cache()

    assert _login(client, "verif.prima@example.com").status_code == 200
