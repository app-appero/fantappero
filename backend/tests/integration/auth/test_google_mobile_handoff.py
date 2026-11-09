"""Mobile Google login handoff: a one-time code crosses the deep link, never a token."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from auth import google_oauth
from auth.google_oauth import GoogleIdentity
from config.settings.loader import reset_settings_cache


@pytest.fixture(autouse=True)
def _google_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_IDS", "test-client-id")
    reset_settings_cache()


def _stub_identity(monkeypatch: pytest.MonkeyPatch, *, sub: str, email: str) -> None:
    identity = GoogleIdentity(sub=sub, email=email, email_verified=True, name="Utente App")
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)


def test_start_returns_a_code_not_a_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_identity(monkeypatch, sub="handoff-sub-1", email="handoff.start@example.com")

    response = client.post("/auth/google/handoff", json={"idToken": "fake"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"code"}
    assert len(body["code"]) > 20


def test_claim_returns_the_same_session_the_direct_endpoint_would(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_identity(monkeypatch, sub="handoff-sub-2", email="handoff.claim@example.com")

    code = client.post("/auth/google/handoff", json={"idToken": "fake"}).json()["code"]
    claimed = client.post("/auth/google/handoff/claim", json={"code": code})

    assert claimed.status_code == 200
    payload = claimed.json()
    assert payload["accessToken"]
    assert payload["refreshToken"]
    assert payload["user"]["displayName"] == "Utente App"

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {payload['accessToken']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["id"] == payload["user"]["id"]


def test_a_code_can_only_be_claimed_once(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_identity(monkeypatch, sub="handoff-sub-3", email="handoff.oneshot@example.com")

    code = client.post("/auth/google/handoff", json={"idToken": "fake"}).json()["code"]
    first = client.post("/auth/google/handoff/claim", json={"code": code})
    second = client.post("/auth/google/handoff/claim", json={"code": code})

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["code"] == "mobile_handoff_expired"


def test_an_unknown_or_guessed_code_is_rejected(client: TestClient) -> None:
    response = client.post("/auth/google/handoff/claim", json={"code": "not-a-real-code"})

    assert response.status_code == 400
    assert response.json()["code"] == "mobile_handoff_expired"


def test_start_still_rejects_an_unverified_google_email(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = GoogleIdentity(
        sub="handoff-sub-4",
        email="handoff.unverified@example.com",
        email_verified=False,
        name="Senza Verifica",
    )
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)

    response = client.post("/auth/google/handoff", json={"idToken": "fake"})

    assert response.status_code == 401
    assert response.json()["code"] == "google_auth_failed"
