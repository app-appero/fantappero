"""Chi ha quale versione dell'app e notifica della nuova versione (release 1.4, Rosario 23/11).

- l'app 1.4 manda la sua versione in ogni richiesta; delle app 1.2 e 1.3 si sa che chiamano
  ``GET /app/version``; delle altre richieste ``okhttp/`` solo che sono l'app; il sito conta
  solo da un telefono Android (riga ``web-android``), non da computer o iPhone;
- si scrive al più una volta ogni qualche minuto per utente, mai bloccando la richiesta;
- l'operatore vede l'elenco versione per versione (``GET /admin/app-version/users``);
- all'annuncio di una versione parte una notifica, una sola volta, a chi usa l'app Android o il
  sito da Android e non ce l'ha già.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from admin.app_version import ANDROID_APP_VERSION_FLAG_KEY
from app_usage.models import (
    PLATFORM_WEB_ANDROID,
    SOURCE_BROWSER,
    SOURCE_HEADER,
    SOURCE_USER_AGENT,
    SOURCE_VERSION_CHECK,
    UserAppUsage,
)
from app_usage.recorder import reset_app_usage_throttle
from auth.models.tester_allowlist import TesterAllowlistEntry
from auth.models.user import User
from auth.models.user_profile import UserProfile
from database.enums import PlatformRole
from database.models.infrastructure import SystemFlag
from database.session import create_session_factory
from mail.capture import get_captured_emails
from notifications.models import Notification, NotificationEventPreference

PASSWORD = "Password123!"
OKHTTP = {"User-Agent": "okhttp/4.12.0"}
CHROME = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0"}
IPHONE = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "Version/18.1 Mobile/15E148 Safari/604.1"
}
ANDROID_CHROME = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 Chrome/131.0 Mobile"
}
APP_14 = {
    **OKHTTP,
    "X-App-Version": "1.4.0",
    "X-App-Version-Code": "5",
    "X-App-Platform": "android",
}
VERSION_5 = {
    "latestVersionName": "1.4.0",
    "latestVersionCode": 5,
    "downloadUrl": "https://drive.google.com/drive/folders/fantappero-1-4",
    "message": None,
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
def _clean(db_session: Session):
    reset_app_usage_throttle()
    yield
    reset_app_usage_throttle()
    db_session.rollback()
    db_session.execute(delete(UserAppUsage))
    db_session.execute(delete(Notification).where(Notification.dedup_key.like("app_version:%")))
    db_session.execute(
        delete(SystemFlag).where(SystemFlag.key.in_([ANDROID_APP_VERSION_FLAG_KEY, "test_mode"]))
    )
    db_session.execute(delete(TesterAllowlistEntry))
    db_session.commit()


def _login(
    client: TestClient, db_session: Session, email: str, *, operator: bool = False
) -> tuple[dict[str, str], UUID]:
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
    user_id = UUID(login.json()["user"]["id"])
    if operator:
        user = db_session.get(User, user_id)
        assert user is not None
        user.platform_role = PlatformRole.OPERATOR
        db_session.commit()
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}, user_id


def _user(db_session: Session, email: str) -> UUID:
    """Utente creato direttamente (senza accesso: il limite dei tentativi vale per indirizzo)."""
    user = User(
        email=email,
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserProfile(user_id=user.id, display_name=email.split("@")[0]))
    db_session.commit()
    return user.id


def _usage(db_session: Session, user_id: UUID) -> list[UserAppUsage]:
    db_session.expire_all()
    return list(
        db_session.scalars(select(UserAppUsage).where(UserAppUsage.user_id == user_id)).all()
    )


def _set_usage(
    db_session: Session,
    user_id: UUID,
    *,
    source: str,
    code: int | None = None,
    name: str | None = None,
    last_seen: datetime | None = None,
    platform: str = "android",
) -> None:
    seen = last_seen or datetime.now(UTC)
    db_session.add(
        UserAppUsage(
            user_id=user_id,
            platform=platform,
            source=source,
            version_code=code,
            version_name=name,
            first_seen_at=seen - timedelta(days=3),
            last_seen_at=seen,
        )
    )
    db_session.commit()


# --- registrazione dalle richieste ----------------------------------------------------------


def test_l_app_1_4_registra_la_versione_esatta(client: TestClient, db_session: Session) -> None:
    headers, user_id = _login(client, db_session, "appusage-exact@example.com")

    assert client.get("/auth/me", headers={**headers, **APP_14}).status_code == 200

    [row] = _usage(db_session, user_id)
    assert (row.platform, row.source, row.version_name, row.version_code) == (
        "android",
        SOURCE_HEADER,
        "1.4.0",
        5,
    )
    assert row.first_seen_at == row.last_seen_at
    assert row.last_seen_at > datetime.now(UTC) - timedelta(minutes=1)


def test_app_version_senza_intestazioni_vale_app_1_2_o_1_3(
    client: TestClient, db_session: Session
) -> None:
    headers, user_id = _login(client, db_session, "appusage-check@example.com")

    assert client.get("/app/version", headers={**headers, **OKHTTP}).status_code == 200

    [row] = _usage(db_session, user_id)
    assert (row.source, row.version_name, row.version_code) == (SOURCE_VERSION_CHECK, None, None)


def test_okhttp_senza_intestazioni_vale_app_e_non_cancella_quello_che_si_sa(
    client: TestClient, db_session: Session
) -> None:
    headers, user_id = _login(client, db_session, "appusage-okhttp@example.com")

    client.get("/auth/me", headers={**headers, **OKHTTP})
    [row] = _usage(db_session, user_id)
    assert row.source == SOURCE_USER_AGENT

    # Poi chiama /app/version: è un'app 1.2 o 1.3 (subito, senza aspettare).
    client.get("/app/version", headers={**headers, **OKHTTP})
    [row] = _usage(db_session, user_id)
    assert row.source == SOURCE_VERSION_CHECK

    # Aggiornata alla 1.4: versione esatta.
    client.get("/auth/me", headers={**headers, **APP_14})
    [row] = _usage(db_session, user_id)
    assert (row.source, row.version_code) == (SOURCE_HEADER, 5)

    # Un download senza intestazioni dopo i minuti di attesa non toglie la versione esatta.
    reset_app_usage_throttle()
    client.get("/auth/me", headers={**headers, **OKHTTP})
    [row] = _usage(db_session, user_id)
    assert (row.source, row.version_name, row.version_code) == (SOURCE_HEADER, "1.4.0", 5)


def test_il_sito_da_computer_o_iphone_non_registra_nulla(
    client: TestClient, db_session: Session
) -> None:
    headers, user_id = _login(client, db_session, "appusage-web@example.com")

    for browser in (CHROME, IPHONE):
        client.get("/auth/me", headers={**headers, **browser})
        client.get("/app/version", headers={**headers, **browser})
    client.get("/auth/me", headers=headers)  # testclient: né browser né app

    assert _usage(db_session, user_id) == []


def test_il_sito_da_android_registra_una_riga_a_parte(
    client: TestClient, db_session: Session
) -> None:
    """Rosario 23/11: chi visita il sito da Android riceve la notifica della nuova versione."""
    headers, user_id = _login(client, db_session, "appusage-web-android@example.com")

    assert client.get("/auth/me", headers={**headers, **ANDROID_CHROME}).status_code == 200

    [row] = _usage(db_session, user_id)
    assert (row.platform, row.source, row.version_name, row.version_code) == (
        PLATFORM_WEB_ANDROID,
        SOURCE_BROWSER,
        None,
        None,
    )
    long_ago = datetime.now(UTC) - timedelta(hours=2)
    row.last_seen_at = long_ago
    db_session.commit()

    # Stesso limite delle scritture dell'app: poco dopo non si riscrive.
    client.get("/auth/me", headers={**headers, **ANDROID_CHROME})
    [row] = _usage(db_session, user_id)
    assert row.last_seen_at == long_ago

    # La stessa persona apre l'app: una riga per l'app, quella del sito resta com'è.
    client.get("/auth/me", headers={**headers, **APP_14})
    rows = {usage.platform: usage for usage in _usage(db_session, user_id)}
    assert set(rows) == {"android", PLATFORM_WEB_ANDROID}
    assert (rows["android"].source, rows["android"].version_code) == (SOURCE_HEADER, 5)
    assert rows[PLATFORM_WEB_ANDROID].source == SOURCE_BROWSER


def test_un_guasto_nella_registrazione_del_sito_non_fa_fallire_la_richiesta(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user_id = _login(client, db_session, "appusage-web-broken@example.com")

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("database giù")

    monkeypatch.setattr("app_usage.recorder.write_observation", _boom)
    response = client.get("/auth/me", headers={**headers, **ANDROID_CHROME})
    assert response.status_code == 200
    assert _usage(db_session, user_id) == []


def test_si_scrive_al_piu_ogni_qualche_minuto(client: TestClient, db_session: Session) -> None:
    headers, user_id = _login(client, db_session, "appusage-throttle@example.com")
    client.get("/auth/me", headers={**headers, **APP_14})
    [row] = _usage(db_session, user_id)
    long_ago = datetime.now(UTC) - timedelta(hours=2)
    row.last_seen_at = long_ago
    db_session.commit()

    # Stessa versione poco dopo: nessuna scrittura.
    for _ in range(3):
        assert client.get("/auth/me", headers={**headers, **APP_14}).status_code == 200
    [row] = _usage(db_session, user_id)
    assert row.last_seen_at == long_ago

    # Una versione nuova si scrive subito.
    newer = {**APP_14, "X-App-Version": "1.4.1", "X-App-Version-Code": "6"}
    client.get("/auth/me", headers={**headers, **newer})
    [row] = _usage(db_session, user_id)
    assert (row.version_name, row.version_code) == ("1.4.1", 6)
    assert row.last_seen_at > long_ago


def test_un_guasto_nella_registrazione_non_fa_fallire_la_richiesta(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers, user_id = _login(client, db_session, "appusage-broken@example.com")

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("database giù")

    monkeypatch.setattr("app_usage.recorder.write_observation", _boom)
    response = client.get("/app/version", headers={**headers, **APP_14})
    assert response.status_code == 200
    assert response.json() == {"android": None}
    assert _usage(db_session, user_id) == []


def test_impersonando_non_si_registra_l_app_dell_operatore(
    client: TestClient, db_session: Session
) -> None:
    operator, operator_id = _login(client, db_session, "appusage-imp-op@example.com", operator=True)
    member_id = _user(db_session, "appusage-imp-member@example.com")
    started = client.post(f"/admin/users/{member_id}/impersonate", headers=operator)
    assert started.status_code == 200, started.text
    as_member = {"Authorization": f"Bearer {started.json()['accessToken']}"}

    assert client.get("/auth/me", headers={**as_member, **APP_14}).status_code == 200
    assert client.get("/auth/me", headers={**as_member, **ANDROID_CHROME}).status_code == 200

    assert _usage(db_session, member_id) == []
    assert _usage(db_session, operator_id) == []


# --- elenco per l'operatore -----------------------------------------------------------------


def test_elenco_solo_per_gli_operatori(client: TestClient, db_session: Session) -> None:
    member, _ = _login(client, db_session, "appusage-member-403@example.com")

    assert client.get("/admin/app-version/users", headers=member).status_code == 403
    assert client.get("/admin/app-version/users").status_code == 401


def test_elenco_versione_per_versione(client: TestClient, db_session: Session) -> None:
    operator, operator_id = _login(
        client, db_session, "appusage-list-op@example.com", operator=True
    )
    new_a = _user(db_session, "appusage-list-a@example.com")
    new_b = _user(db_session, "appusage-list-b@example.com")
    old_14 = _user(db_session, "appusage-list-c@example.com")
    recent = _user(db_session, "appusage-list-d@example.com")
    ancient = _user(db_session, "appusage-list-e@example.com")
    web_only = _user(db_session, "appusage-list-f@example.com")
    deleted = _user(db_session, "appusage-list-g@example.com")
    android_site = _user(db_session, "appusage-list-h@example.com")
    android_site_old = _user(db_session, "appusage-list-i@example.com")
    now = datetime.now(UTC)
    _set_usage(db_session, new_a, source=SOURCE_HEADER, code=6, name="1.4.1", last_seen=now)
    _set_usage(
        db_session,
        new_b,
        source=SOURCE_HEADER,
        code=6,
        name="1.4.1",
        last_seen=now - timedelta(hours=1),
    )
    _set_usage(db_session, old_14, source=SOURCE_HEADER, code=5, name="1.4.0")
    _set_usage(db_session, recent, source=SOURCE_VERSION_CHECK)
    _set_usage(db_session, ancient, source=SOURCE_USER_AGENT)
    _set_usage(db_session, deleted, source=SOURCE_HEADER, code=6, name="1.4.1")
    # Sito da Android: nel gruppo del sito solo chi non ha mai usato l'app.
    _set_usage(
        db_session,
        android_site,
        source=SOURCE_BROWSER,
        platform=PLATFORM_WEB_ANDROID,
        last_seen=now,
    )
    _set_usage(
        db_session,
        android_site_old,
        source=SOURCE_BROWSER,
        platform=PLATFORM_WEB_ANDROID,
        last_seen=now - timedelta(days=1),
    )
    _set_usage(db_session, recent, source=SOURCE_BROWSER, platform=PLATFORM_WEB_ANDROID)
    profile = db_session.get(UserProfile, new_a)
    assert profile is not None
    profile.nickname = "Bomber"
    gone = db_session.get(User, deleted)
    assert gone is not None
    gone.deleted_at = now
    db_session.commit()
    assert client.put("/admin/app-version", headers=operator, json=VERSION_5).status_code == 200

    response = client.get("/admin/app-version/users", headers=operator)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["announced"]["latestVersionCode"] == 5
    groups = body["groups"]
    assert [(g["kind"], g["versionName"], g["versionCode"]) for g in groups] == [
        ("version", "1.4.1", 6),
        ("version", "1.4.0", 5),
        ("unknown_recent", None, None),
        ("unknown", None, None),
        ("web_android", None, None),
        ("never", None, None),
    ]
    newest = groups[0]
    assert newest["upToDate"] is True and groups[1]["upToDate"] is True
    assert newest["platform"] == "android"
    # Il più recente prima; il soprannome è il nome mostrato, il nome resta accanto.
    assert [user["userId"] for user in newest["users"]] == [str(new_a), str(new_b)]
    first = newest["users"][0]
    assert first["displayName"] == "Bomber"
    assert first["name"] == "appusage-list-a"
    assert first["email"] == "appusage-list-a@example.com"
    assert first["lastSeenAt"] is not None and first["firstSeenAt"] is not None
    assert newest["users"][1]["name"] is None
    assert [u["userId"] for u in groups[2]["users"]] == [str(recent)]
    assert [u["userId"] for u in groups[3]["users"]] == [str(ancient)]
    # Il sito da Android: il più recente prima, con l'ultima visita; chi ha anche l'app no.
    site = groups[4]
    assert site["platform"] == "web-android" and site["upToDate"] is False
    assert [u["userId"] for u in site["users"]] == [str(android_site), str(android_site_old)]
    assert all(u["lastSeenAt"] is not None for u in site["users"])
    never_ids = {u["userId"] for u in groups[5]["users"]}
    assert {str(web_only), str(operator_id)} <= never_ids
    assert not {str(android_site), str(android_site_old), str(recent)} & never_ids
    assert all(u["lastSeenAt"] is None for u in groups[5]["users"])
    # L'account eliminato non compare da nessuna parte.
    assert str(deleted) not in {u["userId"] for g in groups for u in g["users"]}
    # Chi usa l'app: il sito da Android non conta.
    assert body["appUsers"] == 5
    assert body["upToDateUsers"] == 3
    assert body["totalUsers"] >= 9

    # Il Riepilogo: «3 utenti aggiornati su 5 che usano l'app».
    overview = client.get("/admin/overview", headers=operator).json()
    assert overview["watch"]["androidAppUsage"] == {"upToDateUsers": 3, "appUsers": 5}


def test_elenco_senza_versione_annunciata(client: TestClient, db_session: Session) -> None:
    operator, _ = _login(client, db_session, "appusage-noann-op@example.com", operator=True)
    user_id = _user(db_session, "appusage-noann@example.com")
    _set_usage(db_session, user_id, source=SOURCE_HEADER, code=5, name="1.4.0")

    body = client.get("/admin/app-version/users", headers=operator).json()

    assert body["announced"] is None
    assert body["upToDateUsers"] == 0
    assert body["groups"][0]["upToDate"] is False
    assert (
        client.get("/admin/overview", headers=operator).json()["watch"]["androidAppUsage"] is None
    )


# --- notifica all'annuncio ------------------------------------------------------------------


def _version_notifications(db_session: Session, user_id: UUID) -> list[Notification]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(Notification).where(
                Notification.user_id == user_id, Notification.dedup_key.like("app_version:%")
            )
        ).all()
    )


def test_l_annuncio_notifica_una_volta_chi_non_ha_la_versione(
    client: TestClient, db_session: Session
) -> None:
    operator, operator_id = _login(
        client, db_session, "appusage-notify-op@example.com", operator=True
    )
    old_headers, old_app = _login(client, db_session, "appusage-notify-old@example.com")
    site_headers, android_site = _login(client, db_session, "appusage-notify-site@example.com")
    desktop_headers, desktop = _login(client, db_session, "appusage-notify-desktop@example.com")
    iphone_headers, iphone = _login(client, db_session, "appusage-notify-iphone@example.com")
    updated = _user(db_session, "appusage-notify-updated@example.com")
    newer = _user(db_session, "appusage-notify-newer@example.com")
    ancient = _user(db_session, "appusage-notify-ancient@example.com")
    never_seen = _user(db_session, "appusage-notify-never@example.com")
    _set_usage(db_session, old_app, source=SOURCE_VERSION_CHECK)
    _set_usage(db_session, ancient, source=SOURCE_USER_AGENT)
    _set_usage(db_session, updated, source=SOURCE_HEADER, code=5, name="1.4.0")
    _set_usage(db_session, newer, source=SOURCE_HEADER, code=6, name="1.4.1")
    # Già aggiornato nell'app e visto anche sul sito da Android: niente notifica.
    _set_usage(db_session, updated, source=SOURCE_BROWSER, platform=PLATFORM_WEB_ANDROID)
    # Il sito da Android si registra dalle richieste; da computer e da iPhone no.
    assert client.get("/auth/me", headers={**site_headers, **ANDROID_CHROME}).status_code == 200
    assert client.get("/auth/me", headers={**desktop_headers, **CHROME}).status_code == 200
    assert client.get("/auth/me", headers={**iphone_headers, **IPHONE}).status_code == 200
    assert [row.platform for row in _usage(db_session, android_site)] == [PLATFORM_WEB_ANDROID]

    saved = client.put(
        "/admin/app-version", headers=operator, json={**VERSION_5, "message": "Più veloce."}
    )

    assert saved.status_code == 200, saved.text
    assert saved.json()["android"]["latestVersionCode"] == 5
    notified = saved.json()["notifiedUsers"]
    # App Android di versione non nota (1.2-1.3 o più vecchia) e sito da Android.
    for user_id in (old_app, ancient, android_site):
        [item] = _version_notifications(db_session, user_id)
        assert item.title == "È disponibile la versione 1.4 dell'app"
        assert item.body == "Più veloce. Apri la notifica per scaricare l'aggiornamento."
        assert item.deep_link == VERSION_5["downloadUrl"]
        assert item.category.value == "sistema"
    # Già aggiornati, solo sito da computer o iPhone, mai visti (operatore compreso): niente.
    for user_id in (updated, newer, desktop, iphone, never_seen, operator_id):
        assert _version_notifications(db_session, user_id) == [], user_id
    assert notified == 3

    # Si vede nell'elenco delle notifiche, con il link.
    listed = client.get("/notifications", headers=old_headers).json()["items"]
    [shown] = [item for item in listed if item["title"].startswith("È disponibile la versione")]
    assert shown["deepLink"] == VERSION_5["downloadUrl"]

    # Risalvare lo stesso versionCode (es. per correggere il link) non rimanda nulla.
    again = client.put(
        "/admin/app-version",
        headers=operator,
        json={**VERSION_5, "downloadUrl": "https://drive.google.com/drive/folders/corretto"},
    )
    assert again.status_code == 200
    assert again.json()["notifiedUsers"] == 0
    assert len(_version_notifications(db_session, old_app)) == 1


def test_l_annuncio_rispetta_le_preferenze_e_le_ore_di_silenzio(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    pushes: list[str] = []

    class _FakePushTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            pushes.append(str(kwargs["user_id"]))

        def apply_async(self, kwargs: dict[str, object], **_options: object) -> None:
            pushes.append(str(kwargs["user_id"]))

    monkeypatch.setattr("notifications.tasks.send_push_task", _FakePushTask())
    operator, _ = _login(client, db_session, "appusage-pref-op@example.com", operator=True)
    normal = _user(db_session, "appusage-pref-normal@example.com")
    no_event = _user(db_session, "appusage-pref-off@example.com")
    no_push = _user(db_session, "appusage-pref-nopush@example.com")
    quiet = _user(db_session, "appusage-pref-quiet@example.com")
    no_category_headers, no_category = _login(client, db_session, "appusage-pref-nocat@example.com")
    for user_id in (normal, no_event, no_push, quiet, no_category):
        _set_usage(db_session, user_id, source=SOURCE_VERSION_CHECK)
        profile = db_session.get(UserProfile, user_id)
        assert profile is not None
        profile.notifications_push = True
        profile.timezone = "Europe/Rome"
    quiet_profile = db_session.get(UserProfile, quiet)
    assert quiet_profile is not None
    hour = datetime.now(ZoneInfo("Europe/Rome")).hour
    quiet_profile.quiet_hours_start_hour = hour
    quiet_profile.quiet_hours_end_hour = (hour + 2) % 24
    db_session.add_all(
        [
            NotificationEventPreference(
                user_id=no_event,
                event_key="sistema.versione_app",
                in_app_enabled=False,
                push_enabled=False,
            ),
            NotificationEventPreference(
                user_id=no_push,
                event_key="sistema.versione_app",
                in_app_enabled=True,
                push_enabled=False,
            ),
        ]
    )
    db_session.commit()
    category_off = client.put(
        "/notifications/preferences",
        headers=no_category_headers,
        json={"category": "sistema", "inAppEnabled": False},
    )
    assert category_off.status_code == 200, category_off.text

    assert client.put("/admin/app-version", headers=operator, json=VERSION_5).status_code == 200

    assert len(_version_notifications(db_session, normal)) == 1
    assert _version_notifications(db_session, no_event) == []
    assert _version_notifications(db_session, no_category) == []
    assert len(_version_notifications(db_session, no_push)) == 1
    assert len(_version_notifications(db_session, quiet)) == 1
    # Push solo a chi ce l'ha accesa, fuori dalle ore di silenzio e con l'evento attivo.
    assert str(normal) in pushes
    assert str(no_push) not in pushes
    assert str(quiet) not in pushes
    assert str(no_event) not in pushes


def test_in_modalita_test_la_notifica_va_solo_a_chi_puo_usare_l_app(
    client: TestClient, db_session: Session
) -> None:
    operator, operator_id = _login(client, db_session, "appusage-tm-op@example.com", operator=True)
    tester = _user(db_session, "appusage-tm-tester@example.com")
    outsider = _user(db_session, "appusage-tm-outsider@example.com")
    for user_id in (operator_id, tester, outsider):
        _set_usage(db_session, user_id, source=SOURCE_USER_AGENT)
    db_session.add(TesterAllowlistEntry(email="appusage-tm-tester@example.com"))
    db_session.commit()
    assert (
        client.put("/admin/test-mode", headers=operator, json={"enabled": True}).status_code == 200
    )

    assert client.put("/admin/app-version", headers=operator, json=VERSION_5).status_code == 200

    assert len(_version_notifications(db_session, tester)) == 1
    assert len(_version_notifications(db_session, operator_id)) == 1
    assert _version_notifications(db_session, outsider) == []


def test_se_la_notifica_non_parte_la_versione_resta_salvata(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator, _ = _login(client, db_session, "appusage-fail-op@example.com", operator=True)

    def _boom(*_args: object, **_kwargs: object) -> int:
        raise RuntimeError("notifiche giù")

    monkeypatch.setattr("app_usage.service.notify_new_app_version", _boom)
    saved = client.put("/admin/app-version", headers=operator, json=VERSION_5)

    assert saved.status_code == 200, saved.text
    assert saved.json() == {"android": VERSION_5, "notifiedUsers": None}
    assert client.get("/admin/app-version", headers=operator).json() == {"android": VERSION_5}
