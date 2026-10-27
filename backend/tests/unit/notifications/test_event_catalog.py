"""Catalogo eventi granulari per le preferenze notifiche (TASK5)."""

from __future__ import annotations

from notifications import templates
from notifications.event_catalog import (
    EVENT_CATEGORY_CALCIATORI,
    EVENT_CATEGORY_SISTEMA,
    EVENT_DEFINITIONS,
    EVENT_KEY_BY_TEMPLATE_KEY,
    EVENT_KEYS,
    event_key_for_template,
)

_EXPECTED_CALCIATORI_EVENTS = {
    "calciatori.gol",
    "calciatori.assist",
    "calciatori.ammonizione",
    "calciatori.espulsione",
    "calciatori.sostituzione",
    "calciatori.infortunio",
    "calciatori.squalifica",
}

_EXPECTED_SISTEMA_EVENTS = {
    "sistema.scambi",
    "sistema.asta",
    "sistema.formazione",
    "sistema.turno_omologato",
    "sistema.avvisi_operatori",
}


def test_calciatori_events_match_the_card_spec() -> None:
    """Un evento per gol/assist/ammonizione/espulsione/sostituzione/infortunio/squalifica."""
    calciatori = {d.event_key for d in EVENT_DEFINITIONS if d.category == EVENT_CATEGORY_CALCIATORI}
    assert calciatori == _EXPECTED_CALCIATORI_EVENTS


def test_sistema_events_match_the_card_spec() -> None:
    """Un evento per scambi/asta/formazione/turno omologato/avvisi operatori."""
    sistema = {d.event_key for d in EVENT_DEFINITIONS if d.category == EVENT_CATEGORY_SISTEMA}
    assert sistema == _EXPECTED_SISTEMA_EVENTS


def test_event_keys_are_unique() -> None:
    keys = [d.event_key for d in EVENT_DEFINITIONS]
    assert len(keys) == len(set(keys))
    assert set(keys) == EVENT_KEYS


def test_every_mapped_template_key_is_registered_in_templates_py() -> None:
    """Ogni template_key granularizzato deve esistere davvero in templates.py,
    altrimenti l'evento non corrisponderebbe a nessuna notifica reale."""
    registered = {key for key, _version in templates._TEMPLATES}
    for template_key in EVENT_KEY_BY_TEMPLATE_KEY:
        assert template_key in registered, f"{template_key} non registrato in templates.py"


def test_every_event_key_in_the_map_is_a_known_event() -> None:
    for event_key in EVENT_KEY_BY_TEMPLATE_KEY.values():
        assert event_key in EVENT_KEYS


def test_event_key_for_template_known_and_unknown() -> None:
    assert event_key_for_template("risultati.gol") == "calciatori.gol"
    assert event_key_for_template("mercato.esito_busta") == "sistema.asta"
    assert event_key_for_template("mercato.asta_live_iniziata") == "sistema.asta"
    # Non ancora granularizzato (inviti lega): resta governato dalla categoria.
    assert event_key_for_template("sistema.invito_lega") is None
    assert event_key_for_template("sconosciuto") is None
