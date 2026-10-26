"""Endpoint /admin/notifications/emails: contratto e permesso (Task 6c).

Stesso approccio di ``test_broadcasts.py::test_sample_list_renders_every_sample``:
le funzioni del router vengono chiamate direttamente (bypassando ``Depends``),
col servizio patchato — non serve un ``TestClient`` per verificare la forma
della risposta e il routing degli errori.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.responses import JSONResponse

from notifications import admin_router
from notifications.admin_router import (
    BroadcastAudience,
    OperatorEmailHistory,
    OperatorEmailSent,
    SendOperatorEmailRequest,
)
from notifications.operator_email_service import OperatorEmailError

ALL_AUDIENCE = {"mode": "all", "leagueIds": [], "userIds": [], "excludeUserIds": []}


def test_request_contract_uses_camel_case_names() -> None:
    body = SendOperatorEmailRequest.model_validate(
        {
            "subject": "Oggetto",
            "body": "Corpo del messaggio",
            "audience": {"mode": "users", "userIds": [str(uuid4())], "excludeUserIds": []},
        }
    )
    assert body.subject == "Oggetto"
    assert body.audience.mode == "users"
    assert isinstance(body.audience, BroadcastAudience)


def test_send_operator_email_returns_id_and_recipient_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_log = SimpleNamespace(id=uuid4(), recipient_count=3)
    monkeypatch.setattr(
        admin_router.operator_email_service,
        "send_operator_email",
        lambda session, **kwargs: fake_log,
    )
    body = SendOperatorEmailRequest.model_validate(
        {"subject": "Oggetto", "body": "Testo", "audience": ALL_AUDIENCE}
    )
    operator = SimpleNamespace(id=uuid4())

    result = admin_router.send_operator_email(
        body, operator=operator, session=MagicMock()  # type: ignore[arg-type]
    )

    assert isinstance(result, OperatorEmailSent)
    assert result.id == str(fake_log.id)
    assert result.recipient_count == 3


def test_send_operator_email_maps_service_error_to_422(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(session: object, **kwargs: object) -> None:
        raise OperatorEmailError("empty_audience", "Nessun destinatario per questo pubblico.")

    monkeypatch.setattr(admin_router.operator_email_service, "send_operator_email", _raise)
    body = SendOperatorEmailRequest.model_validate(
        {"subject": "Oggetto", "body": "Testo", "audience": ALL_AUDIENCE}
    )
    operator = SimpleNamespace(id=uuid4())

    result = admin_router.send_operator_email(
        body, operator=operator, session=MagicMock()  # type: ignore[arg-type]
    )

    assert isinstance(result, JSONResponse)
    assert result.status_code == 422


def test_list_operator_emails_maps_rows_to_history_items(monkeypatch: pytest.MonkeyPatch) -> None:
    row = SimpleNamespace(
        id=uuid4(),
        subject="Oggetto",
        audience_label="Tutti gli utenti",
        recipient_count=10,
        sent_at=SimpleNamespace(isoformat=lambda: "2026-10-26T00:00:00+00:00"),
        created_by_user_id=uuid4(),
    )
    monkeypatch.setattr(
        admin_router.operator_email_service,
        "list_history",
        lambda session, *, page, page_size: ([row], 1),
    )

    result = admin_router.list_operator_emails(
        page=1, page_size=10, _operator=SimpleNamespace(), session=MagicMock()  # type: ignore[arg-type]
    )

    assert isinstance(result, OperatorEmailHistory)
    assert result.total == 1
    item = result.items[0]
    assert item.id == str(row.id)
    assert item.subject == "Oggetto"
    assert item.recipient_count == 10
    assert item.created_by_user_id == str(row.created_by_user_id)
