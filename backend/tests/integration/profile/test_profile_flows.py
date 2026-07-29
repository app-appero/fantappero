"""Integration tests for profile flows (EP02-02)."""

from __future__ import annotations

import io

from tests.integration.auth.conftest import auth_header

_MIN_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _register(client, email: str, password: str = "Secret123") -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def test_profile_defaults_and_update(client) -> None:
    token = _register(client, "profile@example.com")["access_token"]

    me = client.get("/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "profile@example.com"
    assert body["language"] == "it"
    assert body["timezone"] == "Europe/Rome"
    assert body["notifications"] == {"email": True, "push": True}
    assert body["display_name"] is None

    updated = client.patch(
        "/users/me",
        headers=auth_header(token),
        json={
            "display_name": "Mario Rossi",
            "language": "en",
            "timezone": "Europe/London",
            "notifications_email": False,
            "accept_policy": True,
            "policy_version": "2026-01",
        },
    )
    assert updated.status_code == 200
    payload = updated.json()
    assert payload["display_name"] == "Mario Rossi"
    assert payload["language"] == "en"
    assert payload["timezone"] == "Europe/London"
    assert payload["notifications"]["email"] is False
    assert payload["policy_version"] == "2026-01"
    assert payload["policy_consent_at"] is not None


def test_profile_validation_error(client) -> None:
    token = _register(client, "invalid@example.com")["access_token"]
    response = client.patch(
        "/users/me",
        headers=auth_header(token),
        json={"language": "xx"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "profile_validation_error"


def test_profile_policy_version_mismatch(client) -> None:
    token = _register(client, "policy@example.com")["access_token"]
    response = client.patch(
        "/users/me",
        headers=auth_header(token),
        json={"accept_policy": True, "policy_version": "1999-01"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "profile_validation_error"


def test_avatar_upload_and_clear(client) -> None:
    token = _register(client, "avatar@example.com")["access_token"]

    upload = client.post(
        "/users/me/avatar",
        headers=auth_header(token),
        files={"avatar": ("avatar.png", io.BytesIO(_MIN_PNG), "image/png")},
    )
    assert upload.status_code == 200
    assert upload.json()["avatar_url"].startswith("data:image/png;base64,")

    cleared = client.patch(
        "/users/me",
        headers=auth_header(token),
        json={"clear_avatar": True},
    )
    assert cleared.status_code == 200
    assert cleared.json()["avatar_url"] is None


def test_cross_user_profile_forbidden(client) -> None:
    alice = _register(client, "alice-profile@example.com")["access_token"]
    bob = _register(client, "bob-profile@example.com")["access_token"]

    bob_id = client.get("/auth/me", headers=auth_header(bob)).json()["id"]

    cross = client.get(f"/users/{bob_id}", headers=auth_header(alice))
    assert cross.status_code == 403
    assert cross.json()["code"] == "forbidden"

    cross_patch = client.patch(
        "/users/me",
        headers=auth_header(alice),
        json={"display_name": "Hacker"},
    )
    assert cross_patch.status_code == 200

    bob_view = client.get(f"/users/{bob_id}", headers=auth_header(bob))
    assert bob_view.json()["display_name"] is None


def test_unauthenticated_profile_update(client) -> None:
    response = client.patch("/users/me", json={"display_name": "Ghost"})
    assert response.status_code == 401
