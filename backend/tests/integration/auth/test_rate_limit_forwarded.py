"""Dynamic regression for untrusted forwarding headers in auth rate limits."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_login_rate_limit_ignores_client_supplied_forwarded_for(client: TestClient) -> None:
    payload = {"email": "rate-limit-missing@example.com", "password": "WrongPassword123!"}

    for index in range(5):
        response = client.post(
            "/auth/login",
            json=payload,
            headers={"X-Forwarded-For": f"198.18.0.{index + 1}"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/auth/login",
        json=payload,
        headers={"X-Forwarded-For": "198.18.0.250"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limit_exceeded"
