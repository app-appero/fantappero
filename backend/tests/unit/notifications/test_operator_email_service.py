"""Email operatore dal portale: composizione, destinatari, invio, storico (Task 6c).

Stesso approccio di ``test_broadcasts.py``: sessione finta (``MagicMock``),
``resolve_audience``/``audience_label`` patchati (sono già testati per
``broadcast_service`` e vengono riusati qui tali e quali per i destinatari).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from notifications import operator_email_service as svc
from notifications.operator_email_service import OperatorEmailError

ALL = {"mode": "all", "leagueIds": [], "userIds": [], "excludeUserIds": []}


def _patch_audience(
    monkeypatch: pytest.MonkeyPatch, user_ids: list, label: str = "Tutti gli utenti"
) -> None:
    monkeypatch.setattr(svc, "resolve_audience", lambda s, a: user_ids)
    monkeypatch.setattr(svc, "audience_label", lambda *a: label)


def _fake_user(email: str = "u@example.com") -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), email=email)


def _session_with_users(users: list) -> MagicMock:
    session = MagicMock()
    session.scalars.return_value.all.return_value = users
    return session


def test_empty_subject_or_body_is_rejected() -> None:
    with pytest.raises(OperatorEmailError) as exc:
        svc.send_operator_email(
            MagicMock(), created_by=uuid4(), subject="   ", body="testo", audience=ALL
        )
    assert exc.value.code == "empty_message"

    with pytest.raises(OperatorEmailError) as exc:
        svc.send_operator_email(
            MagicMock(), created_by=uuid4(), subject="oggetto", body="", audience=ALL
        )
    assert exc.value.code == "empty_message"


def test_empty_audience_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_audience(monkeypatch, [])
    with pytest.raises(OperatorEmailError) as exc:
        svc.send_operator_email(
            MagicMock(), created_by=uuid4(), subject="Ciao", body="Testo", audience=ALL
        )
    assert exc.value.code == "empty_audience"


def test_send_enqueues_one_email_per_recipient_and_records_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users = [_fake_user("a@example.com"), _fake_user("b@example.com")]
    _patch_audience(monkeypatch, [u.id for u in users], label="2 utenti scelti")
    monkeypatch.setenv("FANTAPPERO_ENV", "test")

    sent: list[dict[str, object]] = []

    class _FakeTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            sent.append(kwargs)

    monkeypatch.setattr("mail.tasks.send_message_task", _FakeTask())

    session = _session_with_users(users)
    created_by = uuid4()
    log = svc.send_operator_email(
        session,
        created_by=created_by,
        subject=" Avviso importante ",
        body=" Leggi questo messaggio. ",
        audience=ALL,
    )

    assert len(sent) == 2
    assert {k["to_email"] for k in sent} == {"a@example.com", "b@example.com"}
    assert all(k["subject"] == "Avviso importante" for k in sent)
    assert all(k["template"] == "operator_email" for k in sent)

    assert log.subject == "Avviso importante"
    assert log.body == "Leggi questo messaggio."
    assert log.recipient_count == 2
    assert log.audience_label == "2 utenti scelti"
    assert log.audience == ALL
    assert log.created_by_user_id == created_by
    assert log.sent_at is not None
    session.add.assert_called_once_with(log)
    session.flush.assert_called_once()


def test_html_body_escapes_user_supplied_text(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _fake_user()
    _patch_audience(monkeypatch, [user.id])
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    sent: list[dict[str, object]] = []

    class _FakeTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            sent.append(kwargs)

    monkeypatch.setattr("mail.tasks.send_message_task", _FakeTask())
    session = _session_with_users([user])

    svc.send_operator_email(
        session,
        created_by=uuid4(),
        subject="S",
        body="<script>alert(1)</script>",
        audience=ALL,
    )

    assert "<script>" not in sent[0]["html_body"]
    assert "&lt;script&gt;" in sent[0]["html_body"]


def test_one_recipient_failure_does_not_block_others_or_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users = [_fake_user("boom@example.com"), _fake_user("ok@example.com")]
    _patch_audience(monkeypatch, [u.id for u in users])
    monkeypatch.setenv("FANTAPPERO_ENV", "test")
    sent: list[dict[str, object]] = []

    class _FlakyTask:
        def apply(self, kwargs: dict[str, object]) -> None:
            if kwargs["to_email"] == "boom@example.com":
                raise RuntimeError("boom")
            sent.append(kwargs)

    monkeypatch.setattr("mail.tasks.send_message_task", _FlakyTask())
    session = _session_with_users(users)

    log = svc.send_operator_email(
        session, created_by=uuid4(), subject="S", body="B", audience=ALL
    )

    assert len(sent) == 1
    assert sent[0]["to_email"] == "ok@example.com"
    # La riga di storico resta registrata anche se un invio è fallito.
    assert log.recipient_count == 2


def test_list_history_returns_rows_and_total() -> None:
    session = MagicMock()
    session.scalar.return_value = 5
    rows = [SimpleNamespace(id=uuid4()) for _ in range(2)]
    session.scalars.return_value.all.return_value = rows

    result_rows, total = svc.list_history(session, page=1, page_size=10)

    assert result_rows == rows
    assert total == 5
