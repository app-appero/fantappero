"""Pilota: chi accede con email e password e non è tester può chiedere l'accesso, come con Google.

Il rifiuto `tester_only` dell'accesso con email porta lo stato della richiesta e il gettone per
inviarla, con lo stesso contenuto dell'accesso con Google; lo stato tester si scopre solo dopo il
controllo della password.
"""

from __future__ import annotations

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

PASSWORD = "Password123!"
FORM = {
    "firstName": "Lucia",
    "lastName": "Bianchi",
    "phone": None,
    "motivation": "Non ho un account Google",
    "consent": True,
}


@pytest.fixture(autouse=True)
def _pilot_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Come su dev e pilota: niente verifica email; Google configurato per il confronto."""
    monkeypatch.setenv("AUTH_EMAIL_VERIFICATION_REQUIRED", "false")
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


def _register(client: TestClient, email: str, display_name: str) -> None:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": display_name},
    )
    assert response.status_code == 201, response.text


def _login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def _operator_with_test_mode(client: TestClient, db_session: Session, email: str) -> dict[str, str]:
    """Operatore (tester di default) che accende la modalità test."""
    _register(client, email, "Operatore")
    login = _login(client, email)
    assert login.status_code == 200, login.text
    user = db_session.get(User, UUID(login.json()["user"]["id"]))
    assert user is not None
    user.platform_role = PlatformRole.OPERATOR
    db_session.commit()
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}
    turned_on = client.put("/admin/test-mode", headers=headers, json={"enabled": True})
    assert turned_on.status_code == 200
    return headers


def _google_body(client: TestClient, monkeypatch: pytest.MonkeyPatch, email: str) -> dict:
    identity = GoogleIdentity(sub=f"sub-{email}", email=email, email_verified=True, name="Utente G")
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)
    response = client.post("/auth/google", json={"idToken": "fake"})
    assert response.status_code == 403, response.text
    return response.json()


def test_non_tester_with_right_password_gets_the_same_request_payload_as_google(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _operator_with_test_mode(client, db_session, "tel.operator@example.com")
    _register(client, "tel.nuovo@example.com", "Lucia Bianchi")

    response = _login(client, "tel.nuovo@example.com")

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "tester_only"
    assert "Non autorizzato" in body["message"]
    assert body["requestStatus"] == "none"
    assert isinstance(body["requestToken"], str) and body["requestToken"]
    assert body["requestEmail"] == "tel.nuovo@example.com"
    # Nome da precompilare: quello del profilo; nome e cognome separati non sono noti.
    assert body["requestName"] == "Lucia Bianchi"
    assert body["requestFirstName"] is None
    assert body["requestLastName"] is None
    assert "accessToken" not in body
    # Stesso contenuto (stesse chiavi) del rifiuto dell'accesso con Google.
    google = _google_body(client, monkeypatch, "tel.google@example.com")
    assert set(body) == set(google)


def test_wrong_password_never_reveals_tester_status(
    client: TestClient, db_session: Session
) -> None:
    _operator_with_test_mode(client, db_session, "tel2.operator@example.com")
    _register(client, "tel2.nuovo@example.com", "Utente Prova")

    wrong = _login(client, "tel2.nuovo@example.com", "PasswordSbagliata1!")
    unknown = _login(client, "tel2.inesistente@example.com")

    for response in (wrong, unknown):
        assert response.status_code == 401
        assert response.json() == {
            "message": "Email o password non validi.",
            "code": "invalid_credentials",
        }


def test_tester_logs_in_with_email_normally(client: TestClient, db_session: Session) -> None:
    operator = _operator_with_test_mode(client, db_session, "tel3.operator@example.com")
    _register(client, "tel3.tester@example.com", "Tester Email")
    added = client.post(
        "/admin/test-mode/testers", headers=operator, json={"email": "tel3.tester@example.com"}
    )
    assert added.status_code == 200

    response = _login(client, "tel3.tester@example.com")

    assert response.status_code == 200, response.text
    assert response.json()["accessToken"]
    assert response.json()["user"]["displayName"] == "Tester Email"


def test_email_request_token_submits_on_the_google_endpoint_and_approval_lets_them_in(
    client: TestClient, db_session: Session
) -> None:
    operator = _operator_with_test_mode(client, db_session, "tel4.operator@example.com")
    _register(client, "tel4.nuovo@example.com", "Lucia Bianchi")
    token = _login(client, "tel4.nuovo@example.com").json()["requestToken"]

    sent = client.post("/auth/tester-requests", json={**FORM, "requestToken": token})
    assert sent.status_code == 201, sent.text
    row = db_session.scalar(
        select(TesterAccessRequest).where(TesterAccessRequest.email == "tel4.nuovo@example.com")
    )
    assert row is not None
    assert (row.first_name, row.last_name, row.status) == ("Lucia", "Bianchi", "pending")

    # Riprovando l'accesso si vede "in valutazione", senza un nuovo gettone.
    pending = _login(client, "tel4.nuovo@example.com")
    assert pending.status_code == 403
    assert pending.json()["requestStatus"] == "pending"
    assert pending.json()["requestSubmittedAt"]
    assert "requestToken" not in pending.json()

    approved = client.post(
        "/admin/tester-requests/decisione",
        headers=operator,
        json={"ids": [str(row.id)], "action": "approve"},
    )
    assert approved.status_code == 200, approved.text
    assert _login(client, "tel4.nuovo@example.com").status_code == 200
