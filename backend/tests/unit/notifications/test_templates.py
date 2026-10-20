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
    proposed = render_notification("mercato.scambio", 1, {"status": "proposed"})
    assert proposed.title == "Nuova proposta di scambio"
    fallback = render_notification("mercato.scambio", 1, {"status": "boh"})
    assert fallback.title == "Aggiornamento scambio"


def test_render_risultati_templates_include_round_number() -> None:
    homologation = render_notification("risultati.omologazione", 1, {"round_number": 7})
    assert "7" in homologation.body
    correction = render_notification("risultati.correzione", 1, {"round_number": 7})
    assert "7" in correction.body


def test_goal_v2_names_player_in_title_and_match_in_body() -> None:
    content = render_notification(
        "risultati.gol",
        2,
        {
            "player": "Lautaro Martinez",
            "minute": 23,
            "fixture_label": "Inter–Juventus",
            "score_label": "1–0",
            "team_name": "Marco FC",
        },
    )
    assert content.title == "Gol di Lautaro Martinez"
    assert content.body == "Inter–Juventus 1–0 al 23' · nel tuo Marco FC"
    assert content.deep_link == "/turni"


def test_player_events_v2_titles() -> None:
    assert (
        render_notification("risultati.espulsione", 2, {"player": "Bastoni", "minute": 61}).title
        == "Espulso Bastoni"
    )
    assert (
        render_notification("risultati.ammonizione", 1, {"player": "Barella"}).title
        == "Ammonito Barella"
    )
    assert (
        render_notification("risultati.infortunio", 2, {"player": "Lookman"}).title
        == "Infortunio per Lookman"
    )
    sub = render_notification(
        "risultati.sostituzione", 1, {"player_out": "Leao", "player_in": "Chiesa", "minute": 70}
    )
    assert sub.title == "Esce Leao, entra Chiesa"
    assert sub.body == "cambio al 70'"


def test_assist_v2_mentions_scorer() -> None:
    content = render_notification(
        "risultati.assist", 1, {"player": "Dumfries", "scorer": "Lautaro"}
    )
    assert content.title == "Assist di Dumfries"
    assert "assist per il gol di Lautaro" in content.body


def test_trade_v2_says_who_and_what() -> None:
    content = render_notification(
        "mercato.scambio",
        2,
        {
            "status": "proposed",
            "other_team": "Giulia United",
            "offered": ["Tonali"],
            "requested": ["Lookman"],
            "offered_credits": 5,
            "expires_label": "il 21 ott alle 20:00",
        },
    )
    assert content.title == "Giulia United ti propone uno scambio"
    assert content.body == "Offre Tonali + 5 cr. · chiede Lookman · scade il 21 ott alle 20:00"
    assert content.deep_link == "/mercato"


def test_trade_v1_still_renders_for_old_notifications() -> None:
    assert (
        render_notification("mercato.scambio", 1, {"status": "proposed"}).title
        == "Nuova proposta di scambio"
    )
