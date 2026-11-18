"""Correzioni QA del 18/11: sessioni, validazione 422, nome e preferenze del profilo."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from mail.capture import get_captured_emails

PASSWORD = "Password123!"


def _login(client: TestClient, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": "Utente Prova"},
    )
    emails = get_captured_emails()
    if emails:
        match = re.search(r"token=([A-Za-z0-9_-]+)", emails[-1].message.text_body)
        if match:
            client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    return login.json()


def _auth(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['accessToken']}"}


def test_validation_errors_never_echo_the_password(client: TestClient) -> None:
    secret = "SegretissimaPassword!42"
    response = client.post(
        "/auth/register", json={"email": "echo.test@example.com", "password": secret}
    )
    assert response.status_code == 422
    assert secret not in response.text
    # Surrogato UTF-16 isolato scritto come escape JSON: non deve dare 500.
    surrogate = client.post(
        "/auth/register",
        content=b'{"email": "x@example.com", "password": "\\ud83d"}',
        headers={"Content-Type": "application/json"},
    )
    assert surrogate.status_code in (400, 422)


def test_logout_closes_the_access_token_and_rotation_keeps_it(client: TestClient) -> None:
    tokens = _login(client, "sess.logout@example.com")
    assert client.get("/auth/me", headers=_auth(tokens)).status_code == 200

    rotated = client.post("/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert rotated.status_code == 200
    new_tokens = rotated.json()
    # Dopo il rinnovo il vecchio token d'accesso resta valido fino alla scadenza naturale.
    assert client.get("/auth/me", headers=_auth(tokens)).status_code == 200

    assert (
        client.post("/auth/logout", json={"refreshToken": new_tokens["refreshToken"]}).status_code
        == 204
    )
    assert client.get("/auth/me", headers=_auth(new_tokens)).status_code == 401
    assert client.get("/auth/me", headers=_auth(tokens)).status_code == 401


def test_reused_refresh_token_closes_the_whole_chain(client: TestClient) -> None:
    tokens = _login(client, "sess.reuse@example.com")
    first = client.post("/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert first.status_code == 200
    second_refresh = first.json()["refreshToken"]

    reused = client.post("/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert reused.status_code == 401
    assert "sessione" in reused.json()["message"].lower()
    assert client.post("/auth/refresh", json={"refreshToken": second_refresh}).status_code == 401
    assert client.get("/auth/me", headers=_auth(first.json())).status_code == 401


def test_profile_rejects_invisible_names_lookalike_nicknames_and_half_quiet_hours(
    client: TestClient,
) -> None:
    tokens = _login(client, "prof.checks@example.com")
    headers = _auth(tokens)
    for bad in ("​", "ㅤ", "Nome\nRiga", "a‮b"):
        response = client.patch("/profile/me", headers=headers, json={"displayName": bad})
        assert response.status_code == 400, (bad, response.text)
        assert response.json()["code"] == "invalid_display_name"
    ok = client.patch("/profile/me", headers=headers, json={"displayName": "José 👨‍👩‍👧"})
    assert ok.status_code == 200, ok.text

    full_width = client.patch("/profile/me", headers=headers, json={"nickname": "ＡＤＭＩＮ"})
    assert full_width.status_code == 200, full_width.text
    assert full_width.json()["nickname"].lower() == "admin"
    punctuation = client.patch("/profile/me", headers=headers, json={"nickname": "..."})
    assert punctuation.status_code == 400

    half = client.patch("/profile/me", headers=headers, json={"quietHoursStartHour": 22})
    assert half.status_code == 400
    assert half.json()["code"] == "incomplete_quiet_hours"
    both = client.patch(
        "/profile/me", headers=headers, json={"quietHoursStartHour": 22, "quietHoursEndHour": 7}
    )
    assert both.status_code == 200, both.text

    export = client.get("/profile/me/export", headers=headers)
    assert export.status_code == 200
    assert "notificationPreferences" in export.json()
