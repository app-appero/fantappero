"""Lista nera, eliminazione utente da parte dell'operatore e operatore protetto."""

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
from auth.models.blocked_account import BlockedAccount
from auth.models.user import User
from config.settings.loader import reset_settings_cache
from database.enums import PlatformRole
from database.session import create_session_factory
from mail.capture import get_captured_emails

PASSWORD = "Password123!"
PROTECTED = "bl.protetto@example.com"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_IDS", "test-client-id")
    monkeypatch.setenv("PROTECTED_OPERATOR_EMAILS", PROTECTED)
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
def _clean_blocklist(db_session: Session):
    db_session.execute(delete(BlockedAccount))
    db_session.commit()
    yield
    db_session.rollback()
    db_session.execute(delete(BlockedAccount))
    db_session.commit()


def _operator(client: TestClient, db_session: Session, email: str) -> tuple[dict[str, str], UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": "Operatore"},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    user_id = UUID(login.json()["user"]["id"])
    user = db_session.get(User, user_id)
    assert user is not None
    user.platform_role = PlatformRole.OPERATOR
    db_session.commit()
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}, user_id


def _google(client: TestClient, monkeypatch: pytest.MonkeyPatch, email: str, sub: str):
    identity = GoogleIdentity(sub=sub, email=email, email_verified=True, name="Utente Prova")
    monkeypatch.setattr(google_oauth, "verify_id_token", lambda *_a, **_k: identity)
    return client.post("/auth/google", json={"idToken": "fake"})


def test_protected_operator_cannot_be_revoked_deleted_or_blocked(
    client: TestClient, db_session: Session
) -> None:
    protected, protected_id = _operator(client, db_session, PROTECTED)
    other, other_id = _operator(client, db_session, "bl.altro@example.com")

    users = client.get("/admin/users?query=bl.", headers=other).json()["items"]
    flags = {item["email"]: item["isProtected"] for item in users}
    assert flags[PROTECTED] is True
    assert flags["bl.altro@example.com"] is False

    revoke = client.post(f"/admin/users/{protected_id}/revoke", headers=other)
    assert revoke.status_code == 409
    assert revoke.json()["code"] == "protected_operator"
    delete_protected = client.post(f"/admin/users/{protected_id}/delete", headers=other)
    assert delete_protected.status_code == 409
    assert delete_protected.json()["code"] == "protected_operator"
    block_protected = client.post("/admin/blocklist", headers=other, json={"email": PROTECTED})
    assert block_protected.status_code == 409

    # Un operatore normale si declassa, ma per eliminarlo va prima revocato.
    delete_operator = client.post(f"/admin/users/{other_id}/delete", headers=protected)
    assert delete_operator.status_code == 409
    assert delete_operator.json()["code"] == "operator_must_be_revoked_first"
    self_delete = client.post(f"/admin/users/{protected_id}/delete", headers=protected)
    assert self_delete.status_code == 409
    assert client.post(f"/admin/users/{other_id}/revoke", headers=protected).status_code == 200


def test_protected_operator_cannot_be_impersonated_but_can_impersonate(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Email propria (il modulo riusa il DB tra i test di questo file: PROTECTED è già
    # registrato dal test precedente) con lo stesso indirizzo marcato protetto.
    protected_email = "bl.protetto.impersona@example.com"
    monkeypatch.setenv("PROTECTED_OPERATOR_EMAILS", f"{PROTECTED},{protected_email}")
    reset_settings_cache()

    protected, protected_id = _operator(client, db_session, protected_email)
    other, other_id = _operator(client, db_session, "bl.impersona@example.com")

    # Un altro operatore (anche uno appena promosso: promote non ha alcun filtro) non può
    # prendere un token come l'account protetto: vanificherebbe la protezione da
    # declassamento/eliminazione sopra testata.
    takeover = client.post(f"/admin/users/{protected_id}/impersonate", headers=other)
    assert takeover.status_code == 409
    assert takeover.json()["code"] == "protected_operator"

    # L'account protetto resta comunque libero di impersonare chiunque altro.
    impersonate_other = client.post(f"/admin/users/{other_id}/impersonate", headers=protected)
    assert impersonate_other.status_code == 200
    assert impersonate_other.json()["user"]["id"] == str(other_id)


def test_impersonation_token_is_short_lived_and_revocable_on_demand(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un token di impersonazione non deve avere la stessa scadenza di una sessione
    normale (12h di default), e deve poter essere chiuso subito dall'operatore
    invece che solo scadere da solo — vedi `admin/service.py::impersonate`."""
    from config.settings.loader import get_api_settings

    operator, _ = _operator(client, db_session, "bl.op6@example.com")
    other, other_id = _operator(client, db_session, "bl.impersona2@example.com")

    started = client.post(f"/admin/users/{other_id}/impersonate", headers=operator)
    assert started.status_code == 200
    body = started.json()
    settings = get_api_settings()
    assert body["expiresIn"] == settings.impersonation_token_expire_minutes * 60
    assert body["expiresIn"] < settings.jwt_access_token_expire_minutes * 60

    impersonated_headers = {"Authorization": f"Bearer {body['accessToken']}"}
    assert client.get("/auth/me", headers=impersonated_headers).status_code == 200

    revoked = client.post(f"/admin/users/{other_id}/impersonate/revoke", headers=operator)
    assert revoked.status_code == 200
    assert revoked.json()["revokedCount"] == 1

    assert client.get("/auth/me", headers=impersonated_headers).status_code == 401
    # Il bersaglio continua a usare la sua sessione normale senza nessun impatto.
    assert client.get("/auth/me", headers=other).status_code == 200

    # Niente da revocare una seconda volta.
    again = client.post(f"/admin/users/{other_id}/impersonate/revoke", headers=operator)
    assert again.status_code == 200
    assert again.json()["revokedCount"] == 0


def test_deleting_a_user_blocks_the_address_for_good(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, _ = _operator(client, db_session, "bl.op2@example.com")
    first = _google(client, monkeypatch, "bl.recidivo@example.com", "sub-recidivo")
    assert first.status_code == 200
    target_id = first.json()["user"]["id"]

    deleted = client.post(f"/admin/users/{target_id}/delete", headers=operator)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["blockedEmail"] == "bl.recidivo@example.com"

    # Account anonimizzato e indirizzo in lista nera.
    row = db_session.get(User, UUID(target_id))
    db_session.refresh(row)
    assert row.deleted_at is not None
    assert row.email != "bl.recidivo@example.com"
    listed = client.get("/admin/blocklist", headers=operator).json()["items"]
    assert [item["email"] for item in listed] == ["bl.recidivo@example.com"]

    # Non rientra né con Google né registrandosi con email e password.
    again = _google(client, monkeypatch, "bl.recidivo@example.com", "sub-recidivo")
    assert again.status_code == 403
    assert again.json()["code"] == "account_blocked"
    register = client.post(
        "/auth/register",
        json={
            "email": "BL.Recidivo@example.com",
            "password": PASSWORD,
            "displayName": "Recidivo",
        },
    )
    assert register.status_code == 403
    assert register.json()["code"] == "account_blocked"
    assert db_session.scalar(select(User.id).where(User.email == "bl.recidivo@example.com")) is None

    # Lo si toglie dalla lista nera: può registrarsi di nuovo.
    entry_id = listed[0]["id"]
    removed = client.delete(f"/admin/blocklist/{entry_id}", headers=operator)
    assert removed.status_code == 200
    assert removed.json()["items"] == []
    assert client.delete(f"/admin/blocklist/{entry_id}", headers=operator).status_code == 404
    # Stesso account Google di prima: ottiene un nuovo account (era il bug «accesso non riuscito»).
    reopened = _google(client, monkeypatch, "bl.recidivo@example.com", "sub-recidivo")
    assert reopened.status_code == 200
    assert reopened.json()["user"]["id"] != target_id


def test_manual_blocklist_entry_stops_existing_users_at_refresh(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, _ = _operator(client, db_session, "bl.op3@example.com")
    session = _google(client, monkeypatch, "bl.manuale@example.com", "sub-manuale")
    assert session.status_code == 200

    added = client.post(
        "/admin/blocklist",
        headers=operator,
        json={"email": " BL.Manuale@Example.com ", "reason": "Comportamento scorretto"},
    )
    assert added.status_code == 200
    item = added.json()["items"][0]
    assert item["email"] == "bl.manuale@example.com"
    assert item["reason"] == "Comportamento scorretto"

    refreshed = client.post("/auth/refresh", json={"refreshToken": session.json()["refreshToken"]})
    assert refreshed.status_code == 403
    assert refreshed.json()["code"] == "account_blocked"
    assert (
        client.post("/admin/blocklist", headers=operator, json={"email": "non-email"}).status_code
        == 400
    )
    # Un operatore non si blocca a mano: prima va revocato.
    op_block = client.post(
        "/admin/blocklist", headers=operator, json={"email": "bl.op3@example.com"}
    )
    assert op_block.status_code == 409


def test_manual_blocklist_entry_stops_an_already_issued_access_token(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bloccare un account deve tagliare fuori anche l'access token già in mano
    all'utente, non solo il prossimo login/refresh — altrimenti l'operatore crede
    di aver tolto l'accesso ma l'utente resta dentro fino alla scadenza del JWT."""
    operator, _ = _operator(client, db_session, "bl.op5@example.com")
    session = _google(client, monkeypatch, "bl.accesstoken@example.com", "sub-accesstoken")
    assert session.status_code == 200
    access_token = session.json()["accessToken"]
    headers = {"Authorization": f"Bearer {access_token}"}

    assert client.get("/auth/me", headers=headers).status_code == 200

    added = client.post(
        "/admin/blocklist",
        headers=operator,
        json={"email": "bl.accesstoken@example.com"},
    )
    assert added.status_code == 200

    blocked = client.get("/auth/me", headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "account_blocked"


def test_delete_without_blocking_lets_the_person_register_again(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, _ = _operator(client, db_session, "bl.op4@example.com")
    first = _google(client, monkeypatch, "bl.semplice@example.com", "sub-semplice")
    assert first.status_code == 200
    target_id = first.json()["user"]["id"]

    deleted = client.post(
        f"/admin/users/{target_id}/delete", headers=operator, json={"block": False}
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["blockedEmail"] is None
    assert client.get("/admin/blocklist", headers=operator).json()["items"] == []

    # Stesso account Google, nessun blocco: rientra con un account nuovo.
    again = _google(client, monkeypatch, "bl.semplice@example.com", "sub-semplice")
    assert again.status_code == 200
    assert again.json()["user"]["id"] != target_id
