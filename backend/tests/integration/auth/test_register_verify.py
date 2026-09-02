"""Register and email verification integration flow."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from mail.capture import get_captured_emails


def _extract_token_from_email_body(body: str) -> str | None:
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    return match.group(1) if match else None


def test_register_verify_login_flow(client: TestClient) -> None:
    register_response = client.post(
        "/auth/register",
        json={
            "email": "marco.rossi@example.com",
            "password": "Password123!",
            "displayName": "Marco Rossi",
        },
    )
    assert register_response.status_code == 201
    emails = get_captured_emails()
    assert len(emails) == 1
    token = _extract_token_from_email_body(emails[0].message.text_body)
    assert token

    login_before = client.post(
        "/auth/login",
        json={"email": "marco.rossi@example.com", "password": "Password123!"},
    )
    assert login_before.status_code == 403

    verify_response = client.post("/auth/verify-email", json={"token": token})
    assert verify_response.status_code == 200

    login_after = client.post(
        "/auth/login",
        json={"email": "marco.rossi@example.com", "password": "Password123!"},
    )
    assert login_after.status_code == 200
    payload = login_after.json()
    assert payload["user"]["displayName"] == "Marco Rossi"
    assert payload["accessToken"]
    assert payload["refreshToken"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {payload['accessToken']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["id"] == payload["user"]["id"]
