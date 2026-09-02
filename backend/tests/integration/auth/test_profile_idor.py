"""Profile isolation — private data only for the authenticated owner."""

from __future__ import annotations

import os
import re

import pytest
import redis
from fastapi.testclient import TestClient

from mail.capture import get_captured_emails


@pytest.fixture(autouse=True)
def _clear_auth_rate_limits() -> None:
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    for key in client.scan_iter("auth:rl:*"):
        client.delete(key)


def _extract_token_from_email_body(body: str) -> str | None:
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    return match.group(1) if match else None


def _register_and_login(client: TestClient, email: str) -> str:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    token = _extract_token_from_email_body(get_captured_emails()[-1].message.text_body)
    assert token
    client.post("/auth/verify-email", json={"token": token})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    return login.json()["accessToken"]


def test_profile_me_never_exposes_other_users(client: TestClient) -> None:
    token_a = _register_and_login(client, "user.a@example.com")
    token_b = _register_and_login(client, "user.b@example.com")

    profile_a = client.get("/profile/me", headers={"Authorization": f"Bearer {token_a}"})
    profile_b = client.get("/profile/me", headers={"Authorization": f"Bearer {token_b}"})

    assert profile_a.status_code == 200
    assert profile_b.status_code == 200
    assert profile_a.json()["email"] == "user.a@example.com"
    assert profile_b.json()["email"] == "user.b@example.com"
    assert profile_a.json()["email"] != profile_b.json()["email"]

    # No public profile-by-id endpoint exists.
    foreign = client.get("/profile/user.b@example.com")
    assert foreign.status_code == 404
