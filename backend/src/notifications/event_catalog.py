"""Catalogo degli eventi granulari per le preferenze notifiche (TASK5).

Prima di questa card le preferenze erano solo per categoria (``sistema``,
``formazione``, ``mercato``, ``risultati`` — vedi ``NotificationPreference``
in ``notifications/models.py``): spegnere ``risultati`` toglieva gol,
assist, cartellini, infortuni e turno omologato tutti insieme, senza modo di
tenerne solo alcuni.

Qui si raggruppano i ``template_key`` di ``notifications/templates.py`` in
"eventi" con un senso per chi usa l'app — uno switch per «gol», uno per
«asta», ecc. — ognuno con canali in-app e push indipendenti
(``NotificationEventPreference`` in ``notifications/models.py``).

Un evento può raggruppare più ``template_key`` (es. ``sistema.asta`` copre
tutte le fasi dell'asta a rilanci: iniziata, sorpassato, aggiudicato,
scambio richiesto). Un ``template_key`` non presente in
``EVENT_KEY_BY_TEMPLATE_KEY`` resta governato solo dalla preferenza di
categoria esistente: nessuna regressione per gli eventi non ancora
granularizzati (es. inviti lega).

Nessuna riga in ``notification_event_preferences`` per un dato
(utente, evento) = tutto attivo: è il default sensato richiesto dalla card
per chi non ha ancora toccato le preferenze granulari.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Eventi legati a cosa fa il singolo calciatore in campo.
EVENT_CATEGORY_CALCIATORI = "calciatori"
#: Eventi "di lega": mercato, formazione, risultati ufficiali, avvisi operatori.
EVENT_CATEGORY_SISTEMA = "sistema"


@dataclass(frozen=True)
class NotificationEventDefinition:
    event_key: str
    category: str
    label: str


EVENT_DEFINITIONS: tuple[NotificationEventDefinition, ...] = (
    NotificationEventDefinition("calciatori.gol", EVENT_CATEGORY_CALCIATORI, "Gol"),
    NotificationEventDefinition("calciatori.assist", EVENT_CATEGORY_CALCIATORI, "Assist"),
    NotificationEventDefinition("calciatori.ammonizione", EVENT_CATEGORY_CALCIATORI, "Ammonizione"),
    NotificationEventDefinition("calciatori.espulsione", EVENT_CATEGORY_CALCIATORI, "Espulsione"),
    NotificationEventDefinition(
        "calciatori.sostituzione", EVENT_CATEGORY_CALCIATORI, "Sostituzione"
    ),
    NotificationEventDefinition("calciatori.infortunio", EVENT_CATEGORY_CALCIATORI, "Infortunio"),
    NotificationEventDefinition("calciatori.squalifica", EVENT_CATEGORY_CALCIATORI, "Squalifica"),
    NotificationEventDefinition("sistema.scambi", EVENT_CATEGORY_SISTEMA, "Scambi"),
    NotificationEventDefinition("sistema.asta", EVENT_CATEGORY_SISTEMA, "Asta"),
    NotificationEventDefinition("sistema.formazione", EVENT_CATEGORY_SISTEMA, "Formazione"),
    NotificationEventDefinition(
        "sistema.turno_omologato", EVENT_CATEGORY_SISTEMA, "Turno omologato"
    ),
    NotificationEventDefinition(
        "sistema.avvisi_operatori", EVENT_CATEGORY_SISTEMA, "Avvisi operatori"
    ),
)

EVENT_KEYS: frozenset[str] = frozenset(definition.event_key for definition in EVENT_DEFINITIONS)

EVENT_DEFINITION_BY_KEY: dict[str, NotificationEventDefinition] = {
    definition.event_key: definition for definition in EVENT_DEFINITIONS
}

#: ``template_key`` (notifications/templates.py) -> evento granulare che lo governa.
#: Più template possono condividere lo stesso evento (es. le fasi dell'asta live).
EVENT_KEY_BY_TEMPLATE_KEY: dict[str, str] = {
    "risultati.gol": "calciatori.gol",
    "risultati.assist": "calciatori.assist",
    "risultati.ammonizione": "calciatori.ammonizione",
    "risultati.espulsione": "calciatori.espulsione",
    "risultati.sostituzione": "calciatori.sostituzione",
    "risultati.infortunio": "calciatori.infortunio",
    "risultati.squalifica": "calciatori.squalifica",
    "mercato.scambio": "sistema.scambi",
    "mercato.esito_busta": "sistema.asta",
    "mercato.asta_live_iniziata": "sistema.asta",
    "mercato.asta_live_aggiudicato": "sistema.asta",
    "mercato.asta_live_sorpassato": "sistema.asta",
    "mercato.asta_live_scambio_richiesto": "sistema.asta",
    "formazione.scadenza_turno": "sistema.formazione",
    "risultati.omologazione": "sistema.turno_omologato",
    "risultati.correzione": "sistema.turno_omologato",
    "sistema.generico": "sistema.avvisi_operatori",
}


def event_key_for_template(template_key: str) -> str | None:
    """Evento granulare per un ``template_key``, o ``None`` se non ancora coperto."""
    return EVENT_KEY_BY_TEMPLATE_KEY.get(template_key)
