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
    assert body["nickname"] is None
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


def test_profile_nickname_is_unique_and_used_as_public_name(client: TestClient) -> None:
    first = _register_and_login(client, "nickname1@example.com", "Luca Bianchi")
    second = _register_and_login(client, "nickname2@example.com", "Marco Verdi")
    first_headers = {"Authorization": f"Bearer {first['access']}"}
    second_headers = {"Authorization": f"Bearer {second['access']}"}

    saved = client.patch(
        "/profile/me",
        headers=first_headers,
        json={"nickname": "Luca"},
    )
    assert saved.status_code == 200
    assert saved.json()["displayName"] == "Luca Bianchi"
    assert saved.json()["nickname"] == "Luca"
    assert client.get("/auth/me", headers=first_headers).json()["displayName"] == "Luca"

    duplicate = client.patch(
        "/profile/me",
        headers=second_headers,
        json={"nickname": "luca"},
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["code"] == "nickname_taken"

    cleared = client.patch(
        "/profile/me",
        headers=first_headers,
        json={"nickname": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["nickname"] is None
    assert client.get("/auth/me", headers=first_headers).json()["displayName"] == "Luca Bianchi"


def test_profile_nickname_rejects_cyrillic_lookalike_of_another_nickname(
    client: TestClient,
) -> None:
    """QA 19/11: «qa07nick1119» con la «a» cirillica (U+0430) passava per un nickname diverso."""
    owner = _register_and_login(client, "qa07.nick@example.com", "Qa Sette")
    impostor = _register_and_login(client, "qa06.nick@example.com", "Qa Sei")
    owner_headers = {"Authorization": f"Bearer {owner['access']}"}
    impostor_headers = {"Authorization": f"Bearer {impostor['access']}"}

    saved = client.patch("/profile/me", headers=owner_headers, json={"nickname": "qa07nick1119"})
    assert saved.status_code == 200, saved.text

    cyrillic = client.patch(
        "/profile/me", headers=impostor_headers, json={"nickname": "q\u043007nick1119"}
    )
    assert cyrillic.status_code == 400, cyrillic.text
    assert cyrillic.json()["code"] == "invalid_nickname"
    greek = client.patch(
        "/profile/me", headers=impostor_headers, json={"nickname": "qa07nick111\u03b9"}
    )
    assert greek.status_code == 400, greek.text
    assert greek.json()["code"] == "invalid_nickname"
    assert client.get("/profile/me", headers=impostor_headers).json()["nickname"] is None

    # Le lettere latine accentate restano valide.
    accented = client.patch("/profile/me", headers=impostor_headers, json={"nickname": "Niccolò"})
    assert accented.status_code == 200, accented.text
    assert accented.json()["nickname"] == "Niccolò"


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
    assert "?v=" in avatar_url
    assert (avatar_dir / f"{session['user_id']}.png").is_file()

    replaced = client.post(
        "/profile/me/avatar",
        headers=headers,
        files={"file": ("avatar.png", BytesIO(_MINIMAL_PNG), "image/png")},
    )
    assert replaced.status_code == 200
    replaced_url = replaced.json()["avatarUrl"]
    assert replaced_url.startswith("/media/avatars/")
    assert "?v=" in replaced_url
    assert replaced_url != avatar_url

    removed = client.delete("/profile/me/avatar", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["avatarUrl"] is None

    # Decisione 13 (18/11): un file che inizia come JPEG ma non è un'immagine
    # viene rifiutato, e gli avatar si servono con `nosniff`.
    fake = client.post(
        "/profile/me/avatar",
        headers=headers,
        files={
            "file": (
                "avatar.jpg",
                BytesIO(b"\xff\xd8\xff\xe0<html><script>alert(1)</script></html>"),
                "image/jpeg",
            )
        },
    )
    assert fake.status_code == 400
    assert fake.json()["code"] == "invalid_avatar_format"
    served = client.get(f"/media/avatars/{session['user_id']}.png")
    assert served.headers.get("x-content-type-options") == "nosniff"


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


def test_profile_quiet_hours_set_reject_invalid_and_clear(client: TestClient) -> None:
    session = _register_and_login(client, "quiethours@example.com", "Quiet Hours User")
    headers = {"Authorization": f"Bearer {session['access']}"}

    set_hours = client.patch(
        "/profile/me",
        headers=headers,
        json={"quietHoursStartHour": 22, "quietHoursEndHour": 8},
    )
    assert set_hours.status_code == 200
    body = set_hours.json()
    assert body["quietHoursStartHour"] == 22
    assert body["quietHoursEndHour"] == 8

    invalid = client.patch(
        "/profile/me",
        headers=headers,
        json={"quietHoursStartHour": 24},
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "invalid_quiet_hour"

    cleared = client.patch(
        "/profile/me",
        headers=headers,
        json={"quietHoursStartHour": None, "quietHoursEndHour": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["quietHoursStartHour"] is None
    assert cleared.json()["quietHoursEndHour"] is None


def test_profile_rejected_update_saves_nothing(client: TestClient) -> None:
    """A18i: una PATCH rifiutata con 400 non deve salvare nessuno dei campi inviati."""
    session = _register_and_login(client, "rejected.update@example.com", "Rifiuto Totale")
    headers = {"Authorization": f"Bearer {session['access']}"}

    cleared = client.patch(
        "/profile/me",
        headers=headers,
        json={"quietHoursStartHour": None, "quietHoursEndHour": None},
    )
    assert cleared.status_code == 200
    named = client.patch("/profile/me", headers=headers, json={"nickname": "Rifiuto"})
    assert named.status_code == 200

    # Solo l'inizio del silenzio: la coppia si controlla dopo aver già scritto il campo.
    half_hours = client.patch("/profile/me", headers=headers, json={"quietHoursStartHour": 21})
    assert half_hours.status_code == 400
    assert half_hours.json()["code"] == "incomplete_quiet_hours"

    # Il nome è valido e viene scritto prima che il nickname sia rifiutato.
    bad_nickname = client.patch(
        "/profile/me",
        headers=headers,
        json={"displayName": "x", "nickname": "<x>"},
    )
    assert bad_nickname.status_code == 400
    assert bad_nickname.json()["code"] == "invalid_nickname"

    profile = client.get("/profile/me", headers=headers)
    assert profile.status_code == 200
    body = profile.json()
    assert body["quietHoursStartHour"] is None
    assert body["quietHoursEndHour"] is None
    assert body["displayName"] == "Rifiuto Totale"
    assert body["nickname"] == "Rifiuto"
