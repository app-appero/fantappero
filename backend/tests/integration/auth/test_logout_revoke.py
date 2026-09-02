"""Logout and refresh revocation integration tests."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from mail.capture import get_captured_emails


def _login(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={
            "email": "logout.user@example.com",
            "password": "Password123!",
            "displayName": "Logout User",
        },
    )
    token_match = re.search(
        r"token=([A-Za-z0-9_-]+)",
        get_captured_emails()[-1].message.text_body,
    )
    client.post("/auth/verify-email", json={"token": token_match.group(1)})
    login_response = client.post(
        "/auth/login",
        json={"email": "logout.user@example.com", "password": "Password123!"},
    )
    return login_response.json()


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    tokens = _login(client)
    logout_response = client.post("/auth/logout", json={"refreshToken": tokens["refreshToken"]})
    assert logout_response.status_code == 204

    refresh_response = client.post("/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert refresh_response.status_code == 401
