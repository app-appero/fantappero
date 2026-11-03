"""Dove stanno gli allegati e perché non sono mai raggiungibili come statici."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static_files import FlatStaticFiles
from config.settings.feedback_settings import FeedbackSettingsMixin


def _settings(**values):
    base = {"feedback_storage_path": None, "avatar_storage_path": "/data/avatars"}
    base.update(values)
    holder = SimpleNamespace(**base)
    holder.resolved_feedback_storage_path = (  # type: ignore[attr-defined]
        lambda: FeedbackSettingsMixin.resolved_feedback_storage_path(holder)  # type: ignore[arg-type]
    )
    return holder


def test_default_storage_lives_inside_the_persistent_avatar_volume():
    assert _settings().resolved_feedback_storage_path() == str(
        Path("/data/avatars/feedback-private")
    )


def test_explicit_storage_path_wins_and_blank_is_ignored():
    assert _settings(feedback_storage_path="/srv/fb").resolved_feedback_storage_path() == "/srv/fb"
    assert _settings(feedback_storage_path="  ").resolved_feedback_storage_path() == str(
        Path("/data/avatars/feedback-private")
    )


def test_avatar_mount_serves_avatars_but_never_the_private_subfolder(tmp_path):
    (tmp_path / "feedback-private").mkdir()
    (tmp_path / "feedback-private" / "secret.mp4").write_bytes(b"video")
    (tmp_path / "abc.jpg").write_bytes(b"avatar")
    (tmp_path / ".hidden.jpg").write_bytes(b"hidden")
    app = FastAPI()
    app.mount("/media/avatars", FlatStaticFiles(directory=str(tmp_path)), name="avatars")
    client = TestClient(app)

    assert client.get("/media/avatars/abc.jpg").content == b"avatar"
    assert client.get("/media/avatars/feedback-private/secret.mp4").status_code == 404
    assert client.get("/media/avatars/feedback-private").status_code == 404
    assert client.get("/media/avatars/%2e%2e/etc/passwd").status_code == 404
    assert client.get("/media/avatars/.hidden.jpg").status_code == 404
