"""Unit tests for the versioned notification template registry (EP09-01)."""

from __future__ import annotations

import pytest

from notifications.templates import render_notification


def test_render_sistema_generico_v1_uses_params() -> None:
    content = render_notification(
        "sistema.generico",
        1,
        {"title": "Titolo", "body": "Corpo", "deep_link": "/app/x"},
    )
    assert content.title == "Titolo"
    assert content.body == "Corpo"
    assert content.deep_link == "/app/x"


def test_render_sistema_generico_v1_defaults_missing_deep_link() -> None:
    content = render_notification("sistema.generico", 1, {"title": "T", "body": "B"})
    assert content.deep_link is None


def test_render_notification_unknown_template_raises() -> None:
    with pytest.raises(KeyError):
        render_notification("sconosciuto", 99, {})
