"""QA 21/11: l'accesso con email e password vale come accettazione dell'informativa, come Google.

Le schermate di accesso dicono «Accedendo accetti l'informativa privacy» (e «Registrandoti…»
nel pannello di registrazione) per Google e per email e password, ma il server salvava versione
e data solo con Google: dopo un accesso con email il profilo restava «L'informativa è stata
aggiornata» e `policyVersion` a null. Ora login e registrazione con email la registrano.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.dependencies import reset_db_cache
from auth.models.user import User
from auth.models.user_profile import UserProfile
from config.settings.loader import get_api_settings, reset_settings_cache
from database.session import create_session_factory

PASSWORD = "Password123!"


def _set_env(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()
    reset_db_cache()


@pytest.fixture(autouse=True)
def _no_email_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    """Come su dev e pilota, dove l'ha visto la QA: si accede subito dopo la registrazione."""
    _set_env(monkeypatch, AUTH_EMAIL_VERIFICATION_REQUIRED="false")


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _register(client: TestClient, email: str):
    return client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": "Utente Informativa"},
    )


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


def _profile(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.get("/profile/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _stored_profile(db_session: Session, email: str) -> UserProfile:
    db_session.expire_all()
    profile = db_session.scalar(
        select(UserProfile).join(User, User.id == UserProfile.user_id).where(User.email == email)
    )
    assert profile is not None
    return profile


def test_email_login_records_the_current_policy_version(
    client: TestClient, db_session: Session
) -> None:
    email = "consenso.login@example.com"
    assert _register(client, email).status_code == 201
    # Account creato prima della correzione: nessuna accettazione salvata.
    stored = _stored_profile(db_session, email)
    stored.policy_version = None
    stored.policy_consent_at = None
    db_session.commit()

    body = _profile(client, _login(client, email))

    assert body["currentPolicyVersion"] == get_api_settings().profile_policy_version
    assert body["policyVersion"] == body["currentPolicyVersion"]
    assert body["policyConsentAt"]


@pytest.mark.parametrize("verification_required", ["false", "true"])
def test_email_registration_records_the_current_policy_version(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    verification_required: str,
) -> None:
    _set_env(monkeypatch, AUTH_EMAIL_VERIFICATION_REQUIRED=verification_required)
    email = f"consenso.registrazione.{verification_required}@example.com"

    assert _register(client, email).status_code == 201

    # Già alla registrazione, prima di qualsiasi accesso (e di verificare l'indirizzo).
    stored = _stored_profile(db_session, email)
    assert stored.policy_version == get_api_settings().profile_policy_version
    assert stored.policy_consent_at is not None
    assert stored.display_name == "Utente Informativa"


def test_email_login_after_a_policy_bump_records_the_new_version(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "consenso.aggiornamento@example.com"
    _set_env(monkeypatch, PROFILE_POLICY_VERSION="2026-11b")
    assert _register(client, email).status_code == 201
    before = _profile(client, _login(client, email))
    assert before["policyVersion"] == "2026-11b"
    first_consent_at = datetime.fromisoformat(before["policyConsentAt"])

    # Stessa versione: un nuovo accesso non sposta la data dell'accettazione.
    again = _profile(client, _login(client, email))
    assert again["policyConsentAt"] == before["policyConsentAt"]

    _set_env(monkeypatch, PROFILE_POLICY_VERSION="2026-11c")
    headers = _login(client, email)
    stored = _stored_profile(db_session, email)
    assert stored.policy_version == "2026-11c"

    after = _profile(client, headers)
    assert after["currentPolicyVersion"] == "2026-11c"
    assert after["policyVersion"] == "2026-11c"
    assert datetime.fromisoformat(after["policyConsentAt"]) > first_consent_at


def test_registering_an_existing_address_does_not_touch_its_acceptance(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = "consenso.esistente@example.com"
    _set_env(monkeypatch, PROFILE_POLICY_VERSION="2026-11b")
    assert _register(client, email).status_code == 201

    # Chi ripete la registrazione con un indirizzo già usato potrebbe non esserne il titolare.
    _set_env(monkeypatch, PROFILE_POLICY_VERSION="2026-11c")
    assert _register(client, email).status_code == 201

    assert _stored_profile(db_session, email).policy_version == "2026-11b"


def test_failed_email_login_does_not_record_acceptance(
    client: TestClient, db_session: Session
) -> None:
    email = "consenso.password@example.com"
    assert _register(client, email).status_code == 201
    stored = _stored_profile(db_session, email)
    stored.policy_version = None
    stored.policy_consent_at = None
    db_session.commit()

    wrong = client.post("/auth/login", json={"email": email, "password": "Sbagliata123!"})

    assert wrong.status_code == 401
    stored = _stored_profile(db_session, email)
    assert stored.policy_version is None
    assert stored.policy_consent_at is None
