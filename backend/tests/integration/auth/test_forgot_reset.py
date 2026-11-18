"""Forgot/reset password integration flow."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from mail.capture import get_captured_emails


def _register_and_verify(client: TestClient, email: str, password: str) -> None:
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "displayName": "Utente Test"},
    )
    emails = get_captured_emails()
    token_match = re.search(r"token=([A-Za-z0-9_-]+)", emails[-1].message.text_body)
    assert token_match
    client.post("/auth/verify-email", json={"token": token_match.group(1)})


def test_forgot_reset_login_flow(client: TestClient) -> None:
    email = "reset.user@example.com"
    old_password = "Password123!"
    new_password = "NuovaPassword456!"
    _register_and_verify(client, email, old_password)

    forgot_response = client.post("/auth/forgot-password", json={"email": email})
    assert forgot_response.status_code == 200
    emails = get_captured_emails()
    reset_match = re.search(r"token=([A-Za-z0-9_-]+)", emails[-1].message.text_body)
    assert reset_match

    reset_response = client.post(
        "/auth/reset-password",
        json={"token": reset_match.group(1), "newPassword": new_password},
    )
    assert reset_response.status_code == 200

    old_login = client.post("/auth/login", json={"email": email, "password": old_password})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"email": email, "password": new_password})
    assert new_login.status_code == 200


def test_register_and_reset_reject_common_or_email_passwords(client: TestClient) -> None:
    """Decisione 12 (18/11): password comuni o uguali all'email rifiutate."""
    email = "weak.password@example.com"
    common = client.post(
        "/auth/register",
        json={"email": email, "password": "password1", "displayName": "Debole"},
    )
    assert common.status_code == 400
    assert common.json()["code"] == "password_too_common"
    same = client.post(
        "/auth/register",
        json={"email": email, "password": email.upper(), "displayName": "Debole"},
    )
    assert same.status_code == 400
    assert same.json()["code"] == "password_same_as_email"

    _register_and_verify(client, email, "Password123!")
    client.post("/auth/forgot-password", json={"email": email})
    reset_match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert reset_match
    for weak, code in (("qwertyuiop", "password_too_common"), (email, "password_same_as_email")):
        response = client.post(
            "/auth/reset-password",
            json={"token": reset_match.group(1), "newPassword": weak},
        )
        assert response.status_code == 400, response.text
        assert response.json()["code"] == code
    ok = client.post(
        "/auth/reset-password",
        json={"token": reset_match.group(1), "newPassword": "NuovaPassword456!"},
    )
    assert ok.status_code == 200
