"""Validazioni e notifica della segnalazione utente (senza database)."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import database.models  # noqa: F401  (registra tutti i mapper ORM)
from feedback.service import FeedbackError, FeedbackService, author_name

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 64


def _settings(**overrides):
    base = {
        "feedback_storage_path": "/tmp/feedback-test",
        "feedback_image_max_bytes": 1024,
        "feedback_video_max_bytes": 4096,
        "feedback_max_attachments": 3,
        "feedback_hourly_limit": 10,
        "feedback_media_link_ttl_seconds": 900,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _service(**overrides) -> FeedbackService:
    return FeedbackService(session=None, settings=_settings(**overrides))  # type: ignore[arg-type]


def _create(service: FeedbackService, **kwargs):
    params = {
        "message": "Il pulsante salva non risponde dopo il secondo tocco.",
        "category": "bug",
        "page_context": "/formazione",
        "platform": "web",
        "app_version": None,
        "user_agent": None,
        "uploads": [],
    }
    params.update(kwargs)
    return service.create_report(SimpleNamespace(id=uuid4()), **params)


def test_message_must_be_long_enough():
    with pytest.raises(FeedbackError) as error:
        _create(_service(), message="  non va  ")
    assert error.value.code == "feedback_message_too_short"


def test_message_has_an_upper_limit():
    with pytest.raises(FeedbackError) as error:
        _create(_service(), message="a" * 2001)
    assert error.value.code == "feedback_message_too_long"


def test_category_must_be_known():
    with pytest.raises(FeedbackError) as error:
        _create(_service(), category="spam")
    assert error.value.code == "feedback_invalid_category"


def test_too_many_attachments_are_rejected():
    with pytest.raises(FeedbackError) as error:
        _create(_service(feedback_max_attachments=1), uploads=[JPEG, JPEG])
    assert error.value.code == "feedback_too_many_attachments"


def test_unknown_file_types_are_rejected():
    service = _service()
    with pytest.raises(FeedbackError) as error:
        service._check_upload(b"MZ\x90\x00 not an image")
    assert error.value.code == "feedback_invalid_attachment"


def test_empty_attachment_is_rejected():
    with pytest.raises(FeedbackError) as error:
        _service()._check_upload(b"")
    assert error.value.code == "feedback_empty_attachment"


def test_image_and_video_have_separate_size_limits():
    service = _service(feedback_image_max_bytes=100, feedback_video_max_bytes=1000)
    with pytest.raises(FeedbackError) as error:
        service._check_upload(JPEG + b"0" * 100)
    assert error.value.code == "feedback_attachment_too_large"
    assert error.value.status_code == 413
    # Lo stesso peso è accettato per un video.
    data, content_type = service._check_upload(MP4 + b"0" * 100)
    assert content_type == "video/mp4"


def test_author_name_prefers_nickname_then_display_name_then_email():
    user = SimpleNamespace(email="mario@example.com")
    assert author_name(user, SimpleNamespace(nickname="Mario", display_name="Mario Rossi")) == "Mario"
    assert author_name(user, SimpleNamespace(nickname=" ", display_name="Mario Rossi")) == "Mario Rossi"
    assert author_name(user, None) == "mario@example.com"


class _FakeScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    """Registra la query sugli utenti e restituisce operatori finti."""

    def __init__(self, operator_ids):
        self.statements = []
        self._operator_ids = operator_ids

    def scalars(self, statement):
        self.statements.append(statement)
        return _FakeScalars(self._operator_ids)

    def get(self, _model, _key):
        return None


def test_only_operators_are_notified_and_never_the_author(monkeypatch):
    operators = [uuid4(), uuid4()]
    author = SimpleNamespace(id=uuid4(), email="autore@example.com")
    session = _FakeSession(operators)
    calls = []

    class _FakeNotificationService:
        def __init__(self, _session):
            pass

        def create_notification(self, **kwargs):
            calls.append(kwargs)
            return None, True

    monkeypatch.setattr("feedback.service.NotificationService", _FakeNotificationService)
    report = SimpleNamespace(
        id=uuid4(),
        category="bug",
        message="Il pulsante salva non risponde dopo il secondo tocco.",
        attachments=[object()],
    )
    FeedbackService(session, _settings())._notify_operators(report, author=author)  # type: ignore[arg-type]

    # La query seleziona solo gli utenti con ruolo di piattaforma "operator".
    compiled = session.statements[0].compile()
    assert "platform_role" in str(compiled)
    assert "operator" in {str(value) for value in compiled.params.values()} | {
        getattr(value, "value", "") for value in compiled.params.values()
    }
    # Un avviso per operatore, nessuno all'autore.
    assert [call["user_id"] for call in calls] == operators
    assert author.id not in [call["user_id"] for call in calls]
    first = calls[0]
    assert first["template_key"] == "sistema.feedback_utente"
    assert first["email"] is False and first["push"] is True
    assert first["dedup_key"] == f"feedback:{report.id}"
    assert first["params"]["has_media"] is True
