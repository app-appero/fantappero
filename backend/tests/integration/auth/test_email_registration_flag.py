"""Pilota: registrazione solo con Google (AUTH_EMAIL_REGISTRATION_ENABLED=false)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from auth import google_oauth
from auth.google_oauth import GoogleIdentity
from config.settings.loader import reset_settings_cache
from mail.capture import get_captured_emails

PASSWORD = "Password123!"


def _set_flag(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("AUTH_EMAIL_REGISTRATION_ENABLED", value)
    reset_settings_cache()


@pytest.fixture(autouse=True)
def _google_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_IDS", "test-client-id")
    reset_settings_cache()


def _register(client: TestClient, email: str):
    return client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": "Utente Prova"},
    )


def test_options_default_to_email_registration_enabled(client: TestClient) -> None:
    response = client.get("/auth/options")
    assert response.status_code == 200
    assert response.json() == {"emailRegistrationEnabled": True}
    assert _register(client, "flag.default@example.com").status_code == 201


def test_options_are_public_and_report_the_flag(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_flag(monkeypatch, "false")
    response = client.get("/auth/options")  # senza token: serve alla schermata di accesso
    assert response.status_code == 200
    assert response.json() == {"emailRegistrationEnabled": False}


def test_email_registration_is_refused_and_creates_nothing_when_disabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _set_flag(monkeypatch, "false")
    emails_before = len(get_captured_emails())

    response = _register(client, "flag.spento@example.com")

    assert response.status_code == 403
    assert response.json()["code"] == "email_registration_disabled"
    assert "Google" in response.json()["message"]
    # Nessuna email di verifica e nessun account creato.
    assert len(get_captured_emails()) == emails_before
    login = client.post(
        "/auth/login", json={"email": "flag.spento@example.com", "password": PASSWORD}
    )
    assert login.status_code == 401


def test_google_registration_and_existing_password_logins_keep_working_when_disabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Un account con password creato prima di spegnere la registrazione con email...
    assert _register(client, "flag.esistente@example.com").status_code == 201
    token = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert token
    assert client.post("/auth/verify-email", json={"token": token.group(1)}).status_code == 200

    _set_flag(monkeypatch, "false")

    # ...continua ad accedere con email e password,
    login = client.post(
        "/auth/login", json={"email": "flag.esistente@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200, login.text

    # ...e con Google si crea un account nuovo, già verificato, senza alcuna email.
    emails_before = len(get_captured_emails())
    identity = GoogleIdentity(
        sub="google-sub-flag",
        email="flag.google@example.com",
        email_verified=True,
        name="Utente Google",
    )
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)
    google = client.post("/auth/google", json={"idToken": "fake"})
    assert google.status_code == 200, google.text
    assert google.json()["accessToken"]
    assert len(get_captured_emails()) == emails_before


def test_google_login_records_policy_acceptance(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = GoogleIdentity(
        sub="google-sub-policy",
        email="policy.google@example.com",
        email_verified=True,
        name="Utente Privacy",
    )
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)
    google = client.post("/auth/google", json={"idToken": "fake"})
    assert google.status_code == 200, google.text
    headers = {"Authorization": f"Bearer {google.json()['accessToken']}"}

    profile = client.get("/profile/me", headers=headers)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["policyVersion"] == body["currentPolicyVersion"]
    assert body["policyConsentAt"]
