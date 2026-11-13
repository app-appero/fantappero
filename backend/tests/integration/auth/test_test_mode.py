"""Modalità test del pilota: accesso riservato ai tester (e agli operatori)."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth import google_oauth
from auth.google_oauth import GoogleIdentity
from auth.models.tester_allowlist import TesterAllowlistEntry
from auth.models.tester_request import TesterAccessRequest
from auth.models.user import User
from config.settings.loader import reset_settings_cache
from database.enums import PlatformRole
from database.models.infrastructure import SystemFlag
from database.session import create_session_factory
from mail.capture import get_captured_emails

PASSWORD = "Password123!"


@pytest.fixture(autouse=True)
def _google_client_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_IDS", "test-client-id")
    reset_settings_cache()


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _reset_test_mode(db_session: Session):
    """Il database è condiviso dal modulo: la modalità test non deve restare accesa."""
    db_session.execute(delete(TesterAllowlistEntry))
    db_session.execute(delete(TesterAccessRequest))
    db_session.commit()
    yield
    db_session.rollback()
    db_session.execute(delete(SystemFlag).where(SystemFlag.key == "test_mode"))
    db_session.execute(delete(TesterAllowlistEntry))
    db_session.execute(delete(TesterAccessRequest))
    db_session.commit()


def _google(client: TestClient, monkeypatch: pytest.MonkeyPatch, email: str, sub: str):
    identity = GoogleIdentity(sub=sub, email=email, email_verified=True, name="Utente Prova")
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)
    return client.post("/auth/google", json={"idToken": "fake"})


def _operator(client: TestClient, db_session: Session, email: str) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": "Operatore"},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    user = db_session.get(User, UUID(login.json()["user"]["id"]))
    assert user is not None
    user.platform_role = PlatformRole.OPERATOR
    db_session.commit()
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_test_mode_blocks_unlisted_google_accounts_and_creates_nothing(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator = _operator(client, db_session, "tm.operator@example.com")

    # Modalità spenta (default): chiunque può entrare.
    assert _google(client, monkeypatch, "tm.libero@example.com", "sub-libero").status_code == 200

    state = client.get("/admin/test-mode", headers=operator)
    assert state.status_code == 200
    assert state.json() == {"enabled": False, "testers": []}

    on = client.put("/admin/test-mode", headers=operator, json={"enabled": True})
    assert on.status_code == 200
    assert on.json()["enabled"] is True

    # Estraneo: rifiutato e nessun account creato.
    blocked = _google(client, monkeypatch, "tm.estraneo@example.com", "sub-estraneo")
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "tester_only"
    assert "Non autorizzato" in blocked.json()["message"]
    created = db_session.scalar(select(User).where(User.email == "tm.estraneo@example.com"))
    assert created is None

    # Autorizzato prima del primo accesso (anche con maiuscole): entra.
    added = client.post(
        "/admin/test-mode/testers", headers=operator, json={"email": " TM.Tester@Example.com "}
    )
    assert added.status_code == 200
    assert [item["email"] for item in added.json()["testers"]] == ["tm.tester@example.com"]
    assert _google(client, monkeypatch, "tm.tester@example.com", "sub-tester").status_code == 200

    # Un account già esistente ma non in lista viene bloccato dal rinnovo della sessione.
    first = _google(client, monkeypatch, "tm.libero@example.com", "sub-libero")
    assert first.status_code == 403
    client.put("/admin/test-mode", headers=operator, json={"enabled": False})
    reopened = _google(client, monkeypatch, "tm.libero@example.com", "sub-libero")
    assert reopened.status_code == 200
    refresh_token = reopened.json()["refreshToken"]
    client.put("/admin/test-mode", headers=operator, json={"enabled": True})
    assert client.post("/auth/refresh", json={"refreshToken": refresh_token}).status_code == 403

    # L'operatore è tester di default, anche con password.
    login = client.post(
        "/auth/login", json={"email": "tm.operator@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    # Un utente con password non in lista è bloccato.
    client.post(
        "/auth/register",
        json={"email": "tm.pwd@example.com", "password": PASSWORD, "displayName": "Pwd"},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    pwd = client.post("/auth/login", json={"email": "tm.pwd@example.com", "password": PASSWORD})
    assert pwd.status_code == 403


def test_users_list_marks_testers_and_testers_can_be_removed(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator = _operator(client, db_session, "tm2.operator@example.com")
    assert _google(client, monkeypatch, "tm2.utente@example.com", "sub-tm2").status_code == 200

    users = client.get("/admin/users?query=tm2.", headers=operator).json()["items"]
    by_email = {item["email"]: item for item in users}
    assert by_email["tm2.operator@example.com"]["isTester"] is True  # operatore
    assert by_email["tm2.utente@example.com"]["isTester"] is False

    added = client.post(
        "/admin/test-mode/testers", headers=operator, json={"email": "tm2.utente@example.com"}
    )
    entry = added.json()["testers"][0]
    assert entry["displayName"]  # ha già un account: si vede il nome

    users = client.get("/admin/users?query=tm2.utente", headers=operator).json()["items"]
    assert users[0]["isTester"] is True

    removed = client.delete(f"/admin/test-mode/testers/{entry['id']}", headers=operator)
    assert removed.status_code == 200
    assert removed.json()["testers"] == []
    missing = client.delete(f"/admin/test-mode/testers/{entry['id']}", headers=operator)
    assert missing.status_code == 404

    invalid = client.post("/admin/test-mode/testers", headers=operator, json={"email": "non-email"})
    assert invalid.status_code == 400

    plain = _google(client, monkeypatch, "tm2.utente@example.com", "sub-tm2")
    token = plain.json()["accessToken"]
    forbidden = client.get("/admin/test-mode", headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 403


FORM = {
    "firstName": "Mario",
    "lastName": "Rossi",
    "phone": "+39 333 1234567",
    "motivation": "Mi piace il fantacalcio",
    "consent": True,
}


def test_non_tester_can_request_access_and_operator_approves(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator = _operator(client, db_session, "req.operator@example.com")
    client.put("/admin/test-mode", headers=operator, json={"enabled": True})

    blocked = _google(client, monkeypatch, "req.nuovo@example.com", "sub-req-nuovo")
    assert blocked.status_code == 403
    body = blocked.json()
    assert body["code"] == "tester_only"
    assert body["requestStatus"] == "none"
    token = body["requestToken"]

    # Senza consenso la richiesta non parte.
    no_consent = client.post(
        "/auth/tester-requests", json={**FORM, "consent": False, "requestToken": token}
    )
    assert no_consent.status_code == 400
    assert no_consent.json()["code"] == "consent_required"
    # Telefono non valido.
    bad_phone = client.post(
        "/auth/tester-requests", json={**FORM, "phone": "abc-def", "requestToken": token}
    )
    assert bad_phone.status_code == 400

    sent = client.post("/auth/tester-requests", json={**FORM, "requestToken": token})
    assert sent.status_code == 201, sent.json()
    again = client.post("/auth/tester-requests", json={**FORM, "requestToken": token})
    assert again.json()["code"] == "tester_request_pending"

    # Nessun account creato, e riprovando l'accesso si vede "in valutazione".
    assert db_session.scalar(select(User).where(User.email == "req.nuovo@example.com")) is None
    pending = _google(client, monkeypatch, "req.nuovo@example.com", "sub-req-nuovo").json()
    assert pending["requestStatus"] == "pending"
    assert "requestToken" not in pending

    listed = client.get("/admin/tester-requests?status=pending", headers=operator)
    assert listed.status_code == 200
    rows = [row for row in listed.json()["requests"] if row["email"] == "req.nuovo@example.com"]
    assert len(rows) == 1
    assert rows[0]["firstName"] == "Mario"
    assert rows[0]["phone"] == "+39 333 1234567"

    approved = client.post(
        "/admin/tester-requests/decisione",
        headers=operator,
        json={"ids": [rows[0]["id"]], "action": "approve"},
    )
    assert approved.status_code == 200
    assert client.get("/admin/test-mode", headers=operator).json()["testers"][0]["email"] == (
        "req.nuovo@example.com"
    )
    # Ora entra con Google come qualunque tester.
    assert _google(client, monkeypatch, "req.nuovo@example.com", "sub-req-nuovo").status_code == 200


def test_rejected_request_blocks_resubmission_and_member_cannot_decide(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator = _operator(client, db_session, "req2.operator@example.com")
    client.put("/admin/test-mode", headers=operator, json={"enabled": True})
    token = _google(client, monkeypatch, "req2.nuovo@example.com", "sub-req2").json()[
        "requestToken"
    ]
    assert (
        client.post("/auth/tester-requests", json={**FORM, "requestToken": token}).status_code
        == 201
    )
    row = db_session.scalar(
        select(TesterAccessRequest).where(TesterAccessRequest.email == "req2.nuovo@example.com")
    )

    # Un utente qualunque non può decidere.
    client.post(
        "/auth/register",
        json={"email": "req2.member@example.com", "password": PASSWORD, "displayName": "Membro"},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post(
        "/auth/login", json={"email": "req2.member@example.com", "password": PASSWORD}
    )
    # (con modalità test accesa un non tester non entra: il rifiuto basta come prova)
    assert login.status_code in (401, 403)
    forbidden = client.post(
        "/admin/tester-requests/decisione", json={"ids": [str(row.id)], "action": "approve"}
    )
    assert forbidden.status_code in (401, 403)

    rejected = client.post(
        "/admin/tester-requests/decisione",
        headers=operator,
        json={"ids": [str(row.id)], "action": "reject", "note": "gruppo al completo"},
    )
    assert rejected.status_code == 200
    status = _google(client, monkeypatch, "req2.nuovo@example.com", "sub-req2").json()
    assert status["requestStatus"] == "rejected"
    assert db_session.scalar(select(User).where(User.email == "req2.nuovo@example.com")) is None


def test_request_token_is_required_and_form_is_closed_when_test_mode_is_off(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator = _operator(client, db_session, "req3.operator@example.com")
    client.put("/admin/test-mode", headers=operator, json={"enabled": True})
    token = _google(client, monkeypatch, "req3.nuovo@example.com", "sub-req3").json()[
        "requestToken"
    ]
    fake = client.post("/auth/tester-requests", json={**FORM, "requestToken": "falso"})
    assert fake.status_code == 400
    assert fake.json()["code"] == "tester_request_token_invalid"

    client.put("/admin/test-mode", headers=operator, json={"enabled": False})
    closed = client.post("/auth/tester-requests", json={**FORM, "requestToken": token})
    assert closed.json()["code"] == "test_mode_off"


def test_old_rejected_requests_are_purged(db_session: Session) -> None:
    from datetime import UTC, datetime, timedelta

    from auth.tester_requests import TesterRequestService

    old = datetime.now(UTC) - timedelta(days=40)
    db_session.add(
        TesterAccessRequest(
            email="vecchia@example.com",
            first_name="A",
            last_name="B",
            phone="+39 333 0000000",
            status="rejected",
            consent_at=old,
            decided_at=old,
        )
    )
    db_session.commit()
    assert TesterRequestService(db_session).purge_old_rejected() == 1
    db_session.commit()
