"""Versioned in-app notification template registry (EP09-01).

Each template is keyed by ``(template_key, template_version)`` so a stored
notification always renders the same content it was created with, even if a
newer template version is registered later. EP09-02/03/04 add their own
templates here as they wire real triggers (kickoff reminders, market/result
events); EP09-01 only ships the registry itself plus one generic system
template used to exercise the platform end-to-end.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

NotificationParams = dict[str, object]


@dataclass(frozen=True)
class NotificationContent:
    title: str
    body: str
    deep_link: str | None = None


NotificationRenderer = Callable[[NotificationParams], NotificationContent]

_TEMPLATES: dict[tuple[str, int], NotificationRenderer] = {}


def register_template(
    template_key: str, version: int
) -> Callable[[NotificationRenderer], NotificationRenderer]:
    def _decorator(renderer: NotificationRenderer) -> NotificationRenderer:
        _TEMPLATES[(template_key, version)] = renderer
        return renderer

    return _decorator


def render_notification(
    template_key: str, template_version: int, params: NotificationParams
) -> NotificationContent:
    renderer = _TEMPLATES.get((template_key, template_version))
    if renderer is None:
        msg = f"Nessun template registrato per {template_key} v{template_version}"
        raise KeyError(msg)
    return renderer(params)


@register_template("sistema.generico", 1)
def _render_sistema_generico(params: NotificationParams) -> NotificationContent:
    title = str(params.get("title", "Notifica"))
    body = str(params.get("body", ""))
    deep_link = params.get("deep_link")
    return NotificationContent(
        title=title,
        body=body,
        deep_link=str(deep_link) if deep_link is not None else None,
    )


@register_template("sistema.invito_lega", 1)
def _render_sistema_invito_lega(params: NotificationParams) -> NotificationContent:
    """Invito nominativo ricevuto (EP13-P07).

    Il deep link porta agli inviti, non alla lega: finché l'invito non è
    accettato il destinatario non ha accesso alla lega.
    """
    league_name = params.get("league_name", "una lega")
    inviter = params.get("inviter_name")
    body = (
        f"{inviter} ti ha invitato a «{league_name}»."
        if inviter
        else f"Hai ricevuto un invito per «{league_name}»."
    )
    return NotificationContent(
        title="Nuovo invito a una lega",
        body=f"{body} Accetta o rifiuta dagli inviti ricevuti.",
        deep_link="/inviti",
    )


@register_template("formazione.scadenza_turno", 1)
def _render_formazione_scadenza_turno(params: NotificationParams) -> NotificationContent:
    round_number = params.get("round_number")
    cutoff_local = params.get("cutoff_local")
    return NotificationContent(
        title="Scadenza formazione in arrivo",
        body=(
            f"Il turno {round_number} chiude alle {cutoff_local}. "
            "Salva la formazione prima del fischio d'inizio."
        ),
        deep_link="/formazione",
    )


@register_template("mercato.esito_busta", 1)
def _render_mercato_esito_busta(params: NotificationParams) -> NotificationContent:
    athlete_name = params.get("athlete_name", "un giocatore")
    if params.get("outcome") == "assigned":
        amount = params.get("amount_credits")
        return NotificationContent(
            title="Busta aggiudicata",
            body=f"Hai aggiudicato {athlete_name} per {amount} crediti.",
            deep_link="/mercato",
        )
    return NotificationContent(
        title="Busta non aggiudicata",
        body=f"Non hai aggiudicato {athlete_name}: offerta inferiore.",
        deep_link="/mercato",
    )


_TRADE_STATUS_MESSAGES: dict[str, tuple[str, str]] = {
    "proposed": (
        "Nuova proposta di scambio",
        "Hai ricevuto una proposta di scambio. Aprila dal mercato.",
    ),
    "accepted": ("Scambio accettato", "La tua proposta di scambio è stata accettata."),
    "pending_approval": (
        "Scambio in attesa di approvazione",
        "Lo scambio accettato è in attesa di approvazione dell'amministratore.",
    ),
    "rejected": ("Scambio rifiutato", "La tua proposta di scambio è stata rifiutata."),
    "countered": ("Controproposta ricevuta", "Hai ricevuto una controproposta di scambio."),
    "executed": ("Scambio approvato", "Lo scambio è stato approvato ed eseguito."),
    "rejected_by_admin": (
        "Scambio rifiutato dall'amministratore",
        "Lo scambio approvato dalle parti è stato rifiutato dall'amministratore.",
    ),
}


@register_template("mercato.scambio", 1)
def _render_mercato_scambio(params: NotificationParams) -> NotificationContent:
    status = str(params.get("status"))
    title, body = _TRADE_STATUS_MESSAGES.get(status, ("Aggiornamento scambio", "Stato aggiornato."))
    return NotificationContent(title=title, body=body, deep_link="/mercato")


@register_template("risultati.omologazione", 1)
def _render_risultati_omologazione(params: NotificationParams) -> NotificationContent:
    round_number = params.get("round_number")
    return NotificationContent(
        title="Turno omologato",
        body=f"Il turno {round_number} è stato omologato: il risultato è definitivo.",
        deep_link="/classifica",
    )


@register_template("risultati.correzione", 1)
def _render_risultati_correzione(params: NotificationParams) -> NotificationContent:
    round_number = params.get("round_number")
    return NotificationContent(
        title="Correzione al turno omologato",
        body=(
            f"Il turno {round_number} è stato riaperto per una correzione: "
            "il punteggio sarà ricalcolato."
        ),
        deep_link="/classifica",
    )
