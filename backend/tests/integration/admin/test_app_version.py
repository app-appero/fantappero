"""Versione dell'app Android: lettura per chi usa l'app, scrittura solo per l'operatore."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from admin.app_version import ANDROID_APP_VERSION_FLAG_KEY
from auth.models.user import User
from database.enums import FlagScope, PlatformRole
from database.models.infrastructure import SystemFlag
from database.session import create_session_factory
from mail.capture import get_captured_emails

PASSWORD = "Password123!"
VALID = {
    "latestVersionName": "1.3.0",
    "latestVersionCode": 4,
    "downloadUrl": "https://drive.google.com/drive/folders/prova",
    "message": "Nuova formazione più veloce.",
}


@pytest.fixture
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture(autouse=True)
def _reset_flags(db_session: Session):
    yield
    db_session.rollback()
    db_session.execute(
        delete(SystemFlag).where(SystemFlag.key.in_([ANDROID_APP_VERSION_FLAG_KEY, "test_mode"]))
    )
    db_session.commit()


def _login(client: TestClient, db_session: Session, email: str, *, operator: bool = False):
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": email.split("@")[0]},
    )
    emails = get_captured_emails()
    if emails:
        match = re.search(r"token=([A-Za-z0-9_-]+)", emails[-1].message.text_body)
        if match:
            client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    if operator:
        user = db_session.get(User, UUID(login.json()["user"]["id"]))
        assert user is not None
        user.platform_role = PlatformRole.OPERATOR
        db_session.commit()
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}


def test_senza_configurazione_nessuna_versione(client: TestClient, db_session: Session) -> None:
    member = _login(client, db_session, "appver-empty@example.com")
    operator = _login(client, db_session, "appver-empty-op@example.com", operator=True)

    assert client.get("/app/version", headers=member).json() == {"android": None}
    assert client.get("/admin/app-version", headers=operator).json() == {"android": None}


def test_lettura_richiede_accesso(client: TestClient) -> None:
    assert client.get("/app/version").status_code == 401


def test_operatore_imposta_e_utente_legge(client: TestClient, db_session: Session) -> None:
    member = _login(client, db_session, "appver-member@example.com")
    operator = _login(client, db_session, "appver-op@example.com", operator=True)

    saved = client.put("/admin/app-version", headers=operator, json=VALID)
    assert saved.status_code == 200, saved.text
    # Dalla 1.4 la risposta dice anche quante notifiche della nuova versione sono partite.
    assert saved.json()["android"] == VALID
    assert isinstance(saved.json()["notifiedUsers"], int)

    read = client.get("/app/version", headers=member)
    assert read.status_code == 200
    assert read.json() == {"android": VALID}

    # Un nuovo salvataggio sostituisce il precedente; il messaggio vuoto non c'è.
    newer = {**VALID, "latestVersionName": " 1.4.0 ", "latestVersionCode": 5, "message": "  "}
    assert client.put("/admin/app-version", headers=operator, json=newer).status_code == 200
    assert client.get("/app/version", headers=member).json() == {
        "android": {**VALID, "latestVersionName": "1.4.0", "latestVersionCode": 5, "message": None}
    }


def test_non_operatore_non_scrive(client: TestClient, db_session: Session) -> None:
    member = _login(client, db_session, "appver-forbidden@example.com")

    assert client.put("/admin/app-version", headers=member, json=VALID).status_code == 403
    assert client.get("/admin/app-version", headers=member).status_code == 403
    assert client.get("/app/version", headers=member).json() == {"android": None}


@pytest.mark.parametrize(
    "override",
    [
        {"downloadUrl": "http://drive.google.com/apk"},
        {"downloadUrl": "javascript:alert(1)"},
        {"downloadUrl": "https://"},
        {"downloadUrl": "https://drive.google.com/a b"},
        {"latestVersionCode": 0},
        {"latestVersionCode": -3},
        {"latestVersionCode": "4"},
        {"latestVersionCode": 1.5},
        {"latestVersionName": "versione nuova"},
        {"latestVersionName": ""},
        {"message": "x" * 201},
    ],
)
def test_validazione(client: TestClient, db_session: Session, override: dict) -> None:
    operator = _login(client, db_session, "appver-validation@example.com", operator=True)

    response = client.put("/admin/app-version", headers=operator, json={**VALID, **override})
    assert response.status_code == 422, response.text
    assert client.get("/admin/app-version", headers=operator).json() == {"android": None}


def test_valore_rovinato_vale_nessuna_versione(client: TestClient, db_session: Session) -> None:
    member = _login(client, db_session, "appver-broken@example.com")
    db_session.add(
        SystemFlag(key=ANDROID_APP_VERSION_FLAG_KEY, value="{non json", scope=FlagScope.SYSTEM)
    )
    db_session.commit()

    assert client.get("/app/version", headers=member).json() == {"android": None}


def test_non_tester_non_vede_la_versione(client: TestClient, db_session: Session) -> None:
    member = _login(client, db_session, "appver-nontester@example.com")
    operator = _login(client, db_session, "appver-tm-op@example.com", operator=True)
    assert client.put("/admin/app-version", headers=operator, json=VALID).status_code == 200
    # Modalità test accesa dopo l'accesso: chi non è tester non riceve l'avviso.
    assert (
        client.put("/admin/test-mode", headers=operator, json={"enabled": True}).status_code == 200
    )

    assert client.get("/app/version", headers=member).json() == {"android": None}
    assert client.get("/app/version", headers=operator).json() == {"android": VALID}
