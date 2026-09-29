"""Google Sign-In integration flow (JWKS verification is stubbed, DB is real)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from auth import google_oauth
from auth.google_oauth import GoogleIdentity
from config.settings.loader import reset_settings_cache


def _identity(
    *,
    sub: str,
    email: str,
    email_verified: bool = True,
    name: str = "Test Utente",
) -> GoogleIdentity:
    return GoogleIdentity(sub=sub, email=email, email_verified=email_verified, name=name)


@pytest.fixture(autouse=True)
def _google_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_IDS", "test-client-id")
    reset_settings_cache()


def test_google_login_creates_new_verified_user(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity(
        sub="google-sub-new-user",
        email="nuovo.utente@example.com",
        name="Nuovo Utente",
    )
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)

    response = client.post("/auth/google", json={"idToken": "fake"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["displayName"] == "Nuovo Utente"
    assert payload["accessToken"]
    assert payload["refreshToken"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {payload['accessToken']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["id"] == payload["user"]["id"]


def test_google_login_links_existing_local_account(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    register_response = client.post(
        "/auth/register",
        json={
            "email": "gia.registrato@example.com",
            "password": "Password123!",
            "displayName": "Gia Registrato",
        },
    )
    assert register_response.status_code == 201

    identity = _identity(sub="google-sub-linked-account", email="gia.registrato@example.com")
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)

    response = client.post("/auth/google", json={"idToken": "fake"})

    assert response.status_code == 200
    assert response.json()["user"]["displayName"] == "Gia Registrato"


def test_google_login_reusing_google_sub_logs_in_same_user(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity(sub="google-sub-repeat-login", email="repeat.login@example.com")
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)

    first = client.post("/auth/google", json={"idToken": "fake"})
    second = client.post("/auth/google", json={"idToken": "fake"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["user"]["id"] == second.json()["user"]["id"]


def test_google_login_rejects_unverified_email(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity(
        sub="google-sub-unverified",
        email="non.verificato@example.com",
        email_verified=False,
    )
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)

    response = client.post("/auth/google", json={"idToken": "fake"})

    assert response.status_code == 401
    assert response.json()["code"] == "google_auth_failed"


def test_google_login_created_account_cannot_log_in_with_password(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity(sub="google-sub-no-password", email="solo.google@example.com")
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)
    client.post("/auth/google", json={"idToken": "fake"})

    response = client.post(
        "/auth/login",
        json={"email": "solo.google@example.com", "password": "anything123"},
    )

    assert response.status_code == 401
