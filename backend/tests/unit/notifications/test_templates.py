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


def test_render_mercato_esito_busta_assigned() -> None:
    content = render_notification(
        "mercato.esito_busta",
        1,
        {"outcome": "assigned", "athlete_name": "Bomber", "amount_credits": 42},
    )
    assert "aggiudicat" in content.title.lower()
    assert "Bomber" in content.body
    assert "42" in content.body


def test_render_mercato_esito_busta_lost() -> None:
    content = render_notification(
        "mercato.esito_busta", 1, {"outcome": "lost", "athlete_name": "Bomber"}
    )
    assert "non aggiudicata" in content.title.lower()


def test_render_mercato_scambio_known_and_unknown_status() -> None:
    known = render_notification("mercato.scambio", 1, {"status": "rejected"})
    assert known.title == "Scambio rifiutato"
    fallback = render_notification("mercato.scambio", 1, {"status": "boh"})
    assert fallback.title == "Aggiornamento scambio"


def test_render_risultati_templates_include_round_number() -> None:
    homologation = render_notification("risultati.omologazione", 1, {"round_number": 7})
    assert "7" in homologation.body
    correction = render_notification("risultati.correzione", 1, {"round_number": 7})
    assert "7" in correction.body
