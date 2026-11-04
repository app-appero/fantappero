"""Segnalazioni utente: flusso completo su database, Redis e HTTP reali."""

from __future__ import annotations

import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import PlatformRole
from database.session import create_session_factory
from feedback.models import FeedbackAttachment, FeedbackReport
from mail.capture import get_captured_emails

JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-bytes" * 8
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"video-bytes" * 8
MESSAGE = "Dopo aver salvato la formazione il pulsante resta grigio e non succede nulla."


@pytest.fixture(autouse=True)
def _private_storage(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from config.settings.loader import reset_settings_cache

    monkeypatch.setenv("FEEDBACK_STORAGE_PATH", str(tmp_path / "feedback"))
    reset_settings_cache()


@pytest.fixture
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _register_and_login(
    client: TestClient, db_session: Session, email: str, *, operator: bool = False
) -> tuple[str, UUID]:
    """Registra, verifica, (se serve) promuove a operatore e SOLO poi fa il login.

    Un solo login per utente: l'API limita i tentativi di accesso ravvicinati.
    """
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    if operator:
        user = db_session.scalar(select(User).where(User.email == email))
        assert user is not None
        user.platform_role = PlatformRole.OPERATOR
        db_session.commit()
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200, login.text
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _notifications(client: TestClient, token: str) -> list[dict]:
    response = client.get("/notifications", headers=_auth(token))
    assert response.status_code == 200, response.text
    body = response.json()
    return body["items"] if isinstance(body, dict) else body


def _feedback_titles(client: TestClient, token: str) -> list[str]:
    return [item["title"] for item in _notifications(client, token) if "Nuovo " in item["title"]]


def test_report_reaches_only_operators_with_private_media(
    client: TestClient, db_session: Session
) -> None:
    author_token, _ = _register_and_login(client, db_session, "fb.autore@example.com")
    other_token, _ = _register_and_login(client, db_session, "fb.altro@example.com")
    op1_token, _ = _register_and_login(
        client, db_session, "fb.operatore1@example.com", operator=True
    )
    op2_token, _ = _register_and_login(
        client, db_session, "fb.operatore2@example.com", operator=True
    )

    response = client.post(
        "/feedback",
        headers=_auth(author_token),
        data={
            "message": MESSAGE,
            "category": "bug",
            "pageContext": "/formazione",
            "platform": "web",
            "appVersion": "0.0.0",
        },
        files=[
            ("files", ("foto.jpg", JPEG, "image/jpeg")),
            ("files", ("clip.mp4", MP4, "video/mp4")),
        ],
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["status"] == "new" and created["attachmentCount"] == 2

    # --- notifiche: tutti e soli gli operatori --------------------------------------
    assert len(_feedback_titles(client, op1_token)) == 1
    assert len(_feedback_titles(client, op2_token)) == 1
    assert _feedback_titles(client, author_token) == []
    assert _feedback_titles(client, other_token) == []
    notification = next(
        item for item in _notifications(client, op1_token) if "Nuovo " in item["title"]
    )
    assert notification["deepLink"] == "/admin/feedback"
    assert "allegato" in notification["body"]

    # --- l'utente vede solo le sue segnalazioni, senza dati interni ---------------------
    mine = client.get("/feedback/me", headers=_auth(author_token)).json()
    assert [item["id"] for item in mine] == [created["id"]]
    assert "authorEmail" not in mine[0] and "operatorNote" not in mine[0]
    assert client.get("/feedback/me", headers=_auth(other_token)).json() == []

    # --- l'elenco operatore è riservato agli operatori --------------------------------------
    assert client.get("/admin/feedback", headers=_auth(author_token)).status_code == 403
    assert client.get("/admin/feedback").status_code == 401
    listing = client.get("/admin/feedback", headers=_auth(op1_token))
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["total"] == 1 and body["newCount"] == 1
    item = body["items"][0]
    assert item["authorEmail"] == "fb.autore@example.com"
    assert item["pageContext"] == "/formazione" and item["platform"] == "web"
    assert [a["kind"] for a in item["attachments"]] == ["image", "video"]

    # --- gli allegati si vedono col link firmato, non senza -----------------------------------
    image_url = item["attachments"][0]["url"]
    assert client.get(image_url).content == JPEG
    assert client.get(image_url.split("?")[0]).status_code == 422
    assert client.get(image_url.split("?")[0] + "?token=1.abc").status_code == 403
    video_id = item["attachments"][1]["id"]
    assert client.get(image_url.replace(item["attachments"][0]["id"], video_id)).status_code == 403

    # --- l'operatore gestisce la segnalazione; l'utente ne vede lo stato ----------------------
    update = client.patch(
        f"/admin/feedback/{created['id']}",
        headers=_auth(op1_token),
        json={"status": "resolved", "operatorNote": "Corretto nella prossima versione."},
    )
    assert update.status_code == 200, update.text
    assert update.json()["status"] == "resolved"
    assert update.json()["operatorNote"] == "Corretto nella prossima versione."
    assert (
        client.patch(
            f"/admin/feedback/{created['id']}", headers=_auth(author_token), json={"status": "new"}
        ).status_code
        == 403
    )
    assert client.get("/feedback/me", headers=_auth(author_token)).json()[0]["status"] == "resolved"
    filtered = client.get("/admin/feedback", params={"status": "new"}, headers=_auth(op1_token))
    assert filtered.json()["total"] == 0 and filtered.json()["newCount"] == 0

    # --- sul disco il file ha un nome neutro e il tipo è quello reale ------------------------
    stored = db_session.scalars(
        select(FeedbackAttachment).where(FeedbackAttachment.report_id == UUID(created["id"]))
    ).all()
    assert sorted(a.content_type for a in stored) == ["image/jpeg", "video/mp4"]
    assert all("foto" not in a.stored_name and "clip" not in a.stored_name for a in stored)


def test_invalid_reports_are_rejected_and_leave_no_trace(
    client: TestClient, db_session: Session
) -> None:
    token, _ = _register_and_login(client, db_session, "fb.invalid@example.com")
    before = len(db_session.scalars(select(FeedbackReport)).all())

    too_short = client.post("/feedback", headers=_auth(token), data={"message": "non va"})
    assert too_short.status_code == 422
    assert too_short.json()["code"] == "feedback_message_too_short"

    fake_image = client.post(
        "/feedback",
        headers=_auth(token),
        data={"message": MESSAGE},
        files=[("files", ("foto.png", b"MZ\x90\x00 non sono un'immagine", "image/png"))],
    )
    assert fake_image.status_code == 422
    assert fake_image.json()["code"] == "feedback_invalid_attachment"

    too_many = client.post(
        "/feedback",
        headers=_auth(token),
        data={"message": MESSAGE},
        files=[("files", (f"{i}.jpg", JPEG, "image/jpeg")) for i in range(4)],
    )
    assert too_many.status_code == 422
    assert too_many.json()["code"] == "feedback_too_many_attachments"

    assert client.post("/feedback", data={"message": MESSAGE}).status_code == 401
    db_session.expire_all()
    assert len(db_session.scalars(select(FeedbackReport)).all()) == before


def test_hourly_limit_blocks_spam(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from config.settings.loader import reset_settings_cache

    monkeypatch.setenv("FEEDBACK_HOURLY_LIMIT", "2")
    reset_settings_cache()
    token, _ = _register_and_login(client, db_session, "fb.spam@example.com")
    for _ in range(2):
        assert (
            client.post("/feedback", headers=_auth(token), data={"message": MESSAGE}).status_code
            == 201
        )
    blocked = client.post("/feedback", headers=_auth(token), data={"message": MESSAGE})
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "feedback_rate_limited"


def test_export_includes_reports_and_account_deletion_removes_them_with_their_files(
    client: TestClient, db_session: Session, tmp_path
) -> None:
    token, user_id = _register_and_login(client, db_session, "fb.privacy@example.com")
    created = client.post(
        "/feedback",
        headers=_auth(token),
        data={"message": MESSAGE},
        files=[("files", ("foto.jpg", JPEG, "image/jpeg"))],
    )
    assert created.status_code == 201, created.text
    stored_dir = tmp_path / "feedback"
    assert len(list(stored_dir.iterdir())) == 1

    # --- l'esportazione dei dati personali contiene le segnalazioni -------------------------
    exported = client.get("/profile/me/export", headers=_auth(token)).json()
    assert [item["message"] for item in exported["feedback"]] == [MESSAGE]
    assert exported["feedback"][0]["attachmentCount"] == 1

    # --- eliminando l'account spariscono testo, righe e file --------------------------------
    deleted = client.post(
        "/profile/me/delete",
        headers=_auth(token),
        json={"confirmPhrase": "ELIMINA"},
    )
    assert deleted.status_code == 200, deleted.text
    db_session.expire_all()
    assert (
        db_session.scalars(select(FeedbackReport).where(FeedbackReport.user_id == user_id)).all()
        == []
    )
    assert (
        db_session.scalars(
            select(FeedbackAttachment).where(
                FeedbackAttachment.report_id == UUID(created.json()["id"])
            )
        ).all()
        == []
    )
    assert list(stored_dir.iterdir()) == []


def _titles(client: TestClient, token: str, prefix: str) -> list[dict]:
    return [item for item in _notifications(client, token) if item["title"].startswith(prefix)]


def test_author_is_notified_of_status_changes_but_never_sees_internal_notes(
    client: TestClient, db_session: Session
) -> None:
    author_token, _ = _register_and_login(client, db_session, "fb.stato.autore@example.com")
    other_token, _ = _register_and_login(client, db_session, "fb.stato.altro@example.com")
    op_token, _ = _register_and_login(client, db_session, "fb.stato.op@example.com", operator=True)
    report_id = client.post(
        "/feedback", headers=_auth(author_token), data={"message": MESSAGE}
    ).json()["id"]

    def patch(body: dict) -> None:
        response = client.patch(f"/admin/feedback/{report_id}", headers=_auth(op_token), json=body)
        assert response.status_code == 200, response.text

    def author_titles() -> list[str]:
        return [
            item["title"]
            for item in _notifications(client, author_token)
            if "segnalazione" in item["title"]
        ]

    # Solo una nota interna: nessun avviso.
    patch({"operatorNote": "Da verificare con il provider dati."})
    assert author_titles() == []

    # In lavorazione → un avviso, con il link alla pagina delle segnalazioni.
    patch({"status": "in_review"})
    assert author_titles() == ["Stiamo guardando la tua segnalazione"]
    notification = _titles(client, author_token, "Stiamo guardando")[0]
    assert notification["deepLink"] == "/feedback"
    assert MESSAGE[:30] in notification["body"]
    # La nota interna non viaggia mai nell'avviso.
    assert "provider dati" not in notification["body"] + notification["title"]

    # Stesso stato di nuovo: nessun avviso duplicato.
    patch({"status": "in_review"})
    assert len(author_titles()) == 1

    # Risolta → secondo avviso. Riaperta → nessuno. Risolta ancora → di nuovo un avviso.
    patch({"status": "resolved"})
    assert "La tua segnalazione è stata risolta" in author_titles()
    patch({"status": "new"})
    assert len(author_titles()) == 2
    patch({"status": "resolved"})
    assert author_titles().count("La tua segnalazione è stata risolta") == 2

    patch({"status": "dismissed"})
    assert "La tua segnalazione è stata chiusa" in author_titles()

    # Gli altri utenti e gli operatori non ricevono mai gli avvisi dell'autore.
    assert [i for i in _notifications(client, other_token) if "segnalazione" in i["title"]] == []
    assert [
        i for i in _notifications(client, op_token) if "La tua segnalazione" in i["title"]
    ] == []


def test_operator_can_physically_delete_a_report_with_its_files(
    client: TestClient, db_session: Session, tmp_path
) -> None:
    author_token, author_id = _register_and_login(client, db_session, "fb.del.autore@example.com")
    op_token, _ = _register_and_login(client, db_session, "fb.del.op@example.com", operator=True)
    created = client.post(
        "/feedback",
        headers=_auth(author_token),
        data={"message": MESSAGE},
        files=[("files", ("a.jpg", JPEG, "image/jpeg")), ("files", ("b.mp4", MP4, "video/mp4"))],
    ).json()
    stored_dir = tmp_path / "feedback"
    assert len(list(stored_dir.iterdir())) == 2
    listing = client.get("/admin/feedback", headers=_auth(op_token)).json()
    media_url = next(i for i in listing["items"] if i["id"] == created["id"])["attachments"][0][
        "url"
    ]
    assert client.get(media_url).status_code == 200

    # Chi non è operatore non può eliminare; una segnalazione inesistente dà 404.
    assert (
        client.delete(f"/admin/feedback/{created['id']}", headers=_auth(author_token)).status_code
        == 403
    )
    assert client.delete(f"/admin/feedback/{created['id']}").status_code == 401
    missing = client.delete(
        "/admin/feedback/00000000-0000-0000-0000-000000000000", headers=_auth(op_token)
    )
    assert missing.status_code == 404 and missing.json()["code"] == "feedback_not_found"
    assert len(list(stored_dir.iterdir())) == 2  # i tentativi respinti non toccano nulla

    # L'operatore elimina: spariscono righe, allegati e file; il link firmato non funziona più.
    deleted = client.delete(f"/admin/feedback/{created['id']}", headers=_auth(op_token))
    assert deleted.status_code == 200 and deleted.json() == {"deleted": True}
    db_session.expire_all()
    assert db_session.get(FeedbackReport, UUID(created["id"])) is None
    assert (
        db_session.scalars(
            select(FeedbackAttachment).where(FeedbackAttachment.report_id == UUID(created["id"]))
        ).all()
        == []
    )
    assert list(stored_dir.iterdir()) == []
    assert client.get(media_url).status_code == 404
    assert client.get("/feedback/me", headers=_auth(author_token)).json() == []
    assert (
        client.delete(f"/admin/feedback/{created['id']}", headers=_auth(op_token)).status_code
        == 404
    )
