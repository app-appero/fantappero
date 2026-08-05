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
