"""Cross-user token isolation tests."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from mail.capture import get_captured_emails


def _register_user(client: TestClient, email: str) -> str | None:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    return match.group(1) if match else None


def test_reset_token_not_reusable_for_other_user(client: TestClient) -> None:
    user_a = "user.a@example.com"
    user_b = "user.b@example.com"
    _register_user(client, user_a)
    _register_user(client, user_b)

    client.post("/auth/forgot-password", json={"email": user_a})
    reset_token = re.search(
        r"token=([A-Za-z0-9_-]+)",
        get_captured_emails()[-1].message.text_body,
    )
    assert reset_token

    first_reset = client.post(
        "/auth/reset-password",
        json={"token": reset_token.group(1), "newPassword": "NuovaPassword1!"},
    )
    assert first_reset.status_code == 200

    second_reset = client.post(
        "/auth/reset-password",
        json={"token": reset_token.group(1), "newPassword": "AltraPassword2!"},
    )
    assert second_reset.status_code == 400
