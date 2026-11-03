"""Prova HTTP delle segnalazioni: multipart, soglia del corpo e link firmati."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import database.models  # noqa: F401  (registra tutti i mapper ORM)
from app.security_middleware import install_body_size_guard
from auth.dependencies import get_db_session
from authorization.dependencies import require_permissions
from config.settings.loader import get_api_settings
from database.enums import Permission
from feedback import media
from feedback.router import get_feedback_service, router

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 4096


class _Service:
    """Registra ciò che l'API passa al servizio; nessun database."""

    def __init__(self, storage):
        self.calls = []
        self.storage = storage
        self.attachment = None

    def create_report(self, user, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id=uuid4(),
            category=kwargs["category"],
            message=kwargs["message"],
            status="new",
            created_at="2026-11-02T10:00:00Z",
            attachments=[object()] * len(kwargs["uploads"]),
        )

    def get_attachment(self, attachment_id):
        return self.attachment

    def attachment_path(self, attachment):
        return self.storage / attachment.stored_name


@pytest.fixture
def client(tmp_path):
    app = FastAPI()
    app.include_router(router)

    @app.post("/altro")
    async def altro(request: Request) -> dict:
        await request.body()
        return {"ok": True}

    install_body_size_guard(app)
    service = _Service(tmp_path)
    app.dependency_overrides[get_feedback_service] = lambda: service
    app.dependency_overrides[get_db_session] = lambda: None
    user = SimpleNamespace(id=uuid4())
    for dependency in (require_permissions(Permission.PROFILE_VIEW),):
        app.dependency_overrides[dependency] = lambda: user
    # require_permissions crea una funzione nuova a ogni chiamata: la sostituisco
    # direttamente sulle rotte.
    for route in app.routes:
        for dep in getattr(route, "dependant", SimpleNamespace(dependencies=[])).dependencies:
            if dep.call is not None and getattr(dep.call, "__name__", "") == "_dependency":
                app.dependency_overrides[dep.call] = lambda: user
    return TestClient(app), service


def test_multipart_report_with_image_reaches_the_service(client):
    http, service = client
    response = http.post(
        "/feedback",
        data={
            "message": "Il pulsante salva non risponde.",
            "category": "bug",
            "pageContext": "/formazione",
            "platform": "web",
        },
        files=[("files", ("screen.png", JPEG, "image/png"))],
    )
    assert response.status_code == 201, response.text
    call = service.calls[0]
    assert call["category"] == "bug" and call["page_context"] == "/formazione"
    assert call["uploads"] == [JPEG]
    assert response.json()["attachmentCount"] == 1


def test_report_without_files_is_valid(client):
    http, service = client
    response = http.post("/feedback", data={"message": "Il pulsante salva non risponde."})
    assert response.status_code == 201, response.text
    assert service.calls[0]["uploads"] == []
    assert service.calls[0]["category"] == "bug"


def test_a_20_mib_video_passes_on_the_feedback_path_but_not_elsewhere(client):
    http, service = client
    big = MP4 + b"0" * (20 * 1024 * 1024)
    ok = http.post(
        "/feedback",
        data={"message": "Il video mostra il problema."},
        files=[("files", ("clip.mp4", big, "video/mp4"))],
    )
    assert ok.status_code == 201, ok.text
    assert len(service.calls[0]["uploads"][0]) == len(big)
    # Sul resto dell'API il limite globale di 10 MiB resta invariato.
    assert http.post("/altro", content=b"0" * (11 * 1024 * 1024)).status_code == 413
    assert http.post("/altro", content=b"0" * 1024).status_code == 200


def test_media_link_requires_a_valid_token(client, tmp_path):
    http, service = client
    attachment = SimpleNamespace(id=uuid4(), stored_name="clip.mp4", content_type="video/mp4")
    service.attachment = attachment
    (tmp_path / "clip.mp4").write_bytes(MP4)
    secret = get_api_settings().resolved_jwt_secret()
    token = media.make_media_token(secret, attachment.id, ttl_seconds=60)

    ok = http.get(f"/feedback/media/{attachment.id}", params={"token": token})
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "video/mp4"
    assert ok.headers["cache-control"] == "private, no-store"
    assert ok.headers["x-content-type-options"] == "nosniff"
    assert ok.content == MP4

    partial = http.get(
        f"/feedback/media/{attachment.id}",
        params={"token": token},
        headers={"Range": "bytes=0-9"},
    )
    assert partial.status_code == 206 and len(partial.content) == 10

    assert http.get(f"/feedback/media/{attachment.id}", params={"token": "x.y"}).status_code == 403
    assert http.get(f"/feedback/media/{uuid4()}", params={"token": token}).status_code == 403
    assert http.get(f"/feedback/media/{attachment.id}").status_code == 422
