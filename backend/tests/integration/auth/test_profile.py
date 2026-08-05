"""Profile API integration tests (EP02-02)."""

from __future__ import annotations

import re
from io import BytesIO

from fastapi.testclient import TestClient

from mail.capture import get_captured_emails

_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _extract_token_from_email_body(body: str) -> str | None:
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    return match.group(1) if match else None


def _register_and_login(client: TestClient, email: str, display_name: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": display_name},
    )
    token = _extract_token_from_email_body(get_captured_emails()[-1].message.text_body)
    assert token
    client.post("/auth/verify-email", json={"token": token})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    payload = login.json()
    return {
        "access": payload["accessToken"],
        "refresh": payload["refreshToken"],
        "user_id": payload["user"]["id"],
    }


def test_profile_get_and_update_flow(client: TestClient) -> None:
    session = _register_and_login(client, "profilo@example.com", "Luca Bianchi")
    headers = {"Authorization": f"Bearer {session['access']}"}

    profile = client.get("/profile/me", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["email"] == "profilo@example.com"
    assert body["displayName"] == "Luca Bianchi"
    assert body["language"] == "it"
    assert body["timezone"] == "Europe/Rome"
    assert body["currentPolicyVersion"]

    update = client.patch(
        "/profile/me",
        headers=headers,
        json={
            "displayName": "Luca B.",
            "timezone": "Europe/London",
            "notificationsEmail": False,
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["displayName"] == "Luca B."
    assert updated["timezone"] == "Europe/London"
    assert updated["notificationsEmail"] is False

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["displayName"] == "Luca B."


def test_profile_requires_authentication(client: TestClient) -> None:
    response = client.get("/profile/me")
    assert response.status_code == 401


def test_profile_update_rejects_invalid_timezone(client: TestClient) -> None:
    session = _register_and_login(client, "tz@example.com", "Tz User")
    headers = {"Authorization": f"Bearer {session['access']}"}
    response = client.patch(
        "/profile/me",
        headers=headers,
        json={"timezone": "Invalid/Zone"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_timezone"


def test_profile_avatar_upload_and_remove(client: TestClient, tmp_path, monkeypatch) -> None:
    avatar_dir = tmp_path / "avatars"
    monkeypatch.setenv("AVATAR_STORAGE_PATH", str(avatar_dir))
    from auth.dependencies import reset_db_cache
    from config.settings.loader import reset_settings_cache

    reset_settings_cache()
    reset_db_cache()

    session = _register_and_login(client, "avatar@example.com", "Avatar User")
    headers = {"Authorization": f"Bearer {session['access']}"}

    upload = client.post(
        "/profile/me/avatar",
        headers=headers,
        files={"file": ("avatar.png", BytesIO(_MINIMAL_PNG), "image/png")},
    )
    assert upload.status_code == 200
    avatar_url = upload.json()["avatarUrl"]
    assert avatar_url.startswith("/media/avatars/")
    assert (avatar_dir / f"{session['user_id']}.png").is_file()

    removed = client.delete("/profile/me/avatar", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["avatarUrl"] is None


def test_profile_policy_consent(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("PROFILE_POLICY_VERSION", "2026-01")
    from auth.dependencies import reset_db_cache
    from config.settings.loader import reset_settings_cache

    reset_settings_cache()
    reset_db_cache()

    session = _register_and_login(client, "policy@example.com", "Policy User")
    headers = {"Authorization": f"Bearer {session['access']}"}

    consent = client.post(
        "/profile/me/policy-consent",
        headers=headers,
        json={"policyVersion": "2026-01", "accepted": True},
    )
    assert consent.status_code == 200
    payload = consent.json()
    assert payload["policyVersion"] == "2026-01"
    assert payload["policyConsentAt"] is not None

    stale = client.post(
        "/profile/me/policy-consent",
        headers=headers,
        json={"policyVersion": "2025-01", "accepted": True},
    )
    assert stale.status_code == 400
    assert stale.json()["code"] == "invalid_policy_version"


def test_profile_empty_update_rejected(client: TestClient) -> None:
    session = _register_and_login(client, "empty@example.com", "Empty User")
    headers = {"Authorization": f"Bearer {session['access']}"}
    response = client.patch("/profile/me", headers=headers, json={})
    assert response.status_code == 400
    assert response.json()["code"] == "empty_update"
