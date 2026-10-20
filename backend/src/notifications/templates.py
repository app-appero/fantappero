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


@register_template("sistema.invito_lega_esito", 1)
def _render_sistema_invito_lega_esito(params: NotificationParams) -> NotificationContent:
    """Esito di un invito nominativo per chi l'ha inviato (EP13-P07)."""
    league_name = params.get("league_name", "una lega")
    coach_name = params.get("coach_name", "Il fantallenatore invitato")
    if params.get("outcome") == "accepted":
        return NotificationContent(
            title="Invito accettato",
            body=f"{coach_name} ha accettato l'invito a «{league_name}».",
            deep_link="/fantallenatori",
        )
    return NotificationContent(
        title="Invito rifiutato",
        body=f"{coach_name} ha rifiutato l'invito a «{league_name}».",
        deep_link="/fantallenatori",
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


@register_template("mercato.asta_live_aggiudicato", 1)
def _render_mercato_asta_live_aggiudicato(params: NotificationParams) -> NotificationContent:
    athlete_name = params.get("athlete_name", "un giocatore")
    amount = params.get("amount_credits")
    return NotificationContent(
        title="Lotto aggiudicato",
        body=f"Hai aggiudicato {athlete_name} per {amount} crediti.",
        deep_link="/mercato",
    )


@register_template("mercato.asta_live_sorpassato", 1)
def _render_mercato_asta_live_sorpassato(params: NotificationParams) -> NotificationContent:
    """Solo la modalità live può notificare un sorpasso: nelle buste chiuse gli
    importi restano nascosti fino alla risoluzione, quindi non esiste un
    concetto di "sorpasso" da comunicare in tempo reale."""
    athlete_name = params.get("athlete_name", "un giocatore")
    return NotificationContent(
        title="Sei stato sorpassato",
        body=f"Un altro fantallenatore ha rilanciato su {athlete_name}.",
        deep_link="/mercato",
    )


@register_template("mercato.asta_live_scambio_richiesto", 1)
def _render_mercato_asta_live_scambio_richiesto(params: NotificationParams) -> NotificationContent:
    athlete_name = params.get("athlete_name", "un giocatore")
    return NotificationContent(
        title="Scelta richiesta: rosa al completo",
        body=(
            f"Hai aggiudicato {athlete_name} ma la tua rosa in quel ruolo è al completo: "
            "scegli chi scambiare."
        ),
        deep_link="/mercato",
    )


@register_template("mercato.asta_live_iniziata", 1)
def _render_mercato_asta_live_iniziata(params: NotificationParams) -> NotificationContent:
    return NotificationContent(
        title="Asta a rilanci iniziata",
        body="La sessione d'asta a rilanci è aperta: raggiungi la lega per partecipare.",
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


def _live_content(title_fmt: str, body_fmt: str, params: NotificationParams) -> NotificationContent:
    minute = params.get("minute")
    suffix = f" al {minute}'" if minute is not None else ""
    player = params.get("player", "Un tuo giocatore")
    return NotificationContent(
        title=title_fmt,
        body=body_fmt.format(player=player, suffix=suffix),
        deep_link="/turni",
    )


@register_template("risultati.gol", 1)
def _render_risultati_gol(params: NotificationParams) -> NotificationContent:
    return _live_content("Gol!", "{player} ha segnato{suffix}.", params)


@register_template("risultati.espulsione", 1)
def _render_risultati_espulsione(params: NotificationParams) -> NotificationContent:
    return _live_content("Espulsione", "{player} è stato espulso{suffix}.", params)


@register_template("risultati.infortunio", 1)
def _render_risultati_infortunio(params: NotificationParams) -> NotificationContent:
    return _live_content("Giocatore infortunato", "{player} risulta infortunato.", params)


@register_template("risultati.squalifica", 1)
def _render_risultati_squalifica(params: NotificationParams) -> NotificationContent:
    return _live_content("Giocatore squalificato", "{player} risulta squalificato.", params)


# -- Versione 2: testi specifici (chi, cosa, dove) -------------------------------------------------


def _join(*parts: object, sep: str = " · ") -> str:
    return sep.join(str(part) for part in parts if part)


def _minute_suffix(params: NotificationParams) -> str:
    minute = params.get("minute")
    return f" al {minute}'" if minute is not None else ""


def _match_line(params: NotificationParams) -> str:
    """«Inter–Juventus 1–0» (solo ciò che si conosce)."""
    return _join(params.get("fixture_label"), params.get("score_label"), sep=" ")


def _team_note(params: NotificationParams) -> str:
    team = params.get("team_name")
    return f"nel tuo {team}" if team else ""


def _live_content_v2(
    title: str, detail: str, params: NotificationParams, *, deep_link: str = "/turni"
) -> NotificationContent:
    body = _join(
        _match_line(params) and f"{_match_line(params)}{detail}" or detail.lstrip(" ·"),
        _team_note(params),
    )
    return NotificationContent(title=title, body=body, deep_link=deep_link)


def _player(params: NotificationParams) -> str:
    return str(params.get("player", "Un tuo giocatore"))


@register_template("risultati.gol", 2)
def _render_risultati_gol_v2(params: NotificationParams) -> NotificationContent:
    return _live_content_v2(f"Gol di {_player(params)}", _minute_suffix(params), params)


@register_template("risultati.assist", 1)
def _render_risultati_assist(params: NotificationParams) -> NotificationContent:
    scorer = params.get("scorer")
    detail = f" · assist per il gol di {scorer}" if scorer else " · assist"
    return _live_content_v2(f"Assist di {_player(params)}", detail, params)


@register_template("risultati.ammonizione", 1)
def _render_risultati_ammonizione(params: NotificationParams) -> NotificationContent:
    return _live_content_v2(
        f"Ammonito {_player(params)}", f" · giallo{_minute_suffix(params)}", params
    )


@register_template("risultati.espulsione", 2)
def _render_risultati_espulsione_v2(params: NotificationParams) -> NotificationContent:
    return _live_content_v2(
        f"Espulso {_player(params)}", f" · rosso{_minute_suffix(params)}", params
    )


@register_template("risultati.sostituzione", 1)
def _render_risultati_sostituzione(params: NotificationParams) -> NotificationContent:
    out_player = params.get("player_out", "un giocatore")
    in_player = params.get("player_in", "un compagno")
    return _live_content_v2(
        f"Esce {out_player}, entra {in_player}", f" · cambio{_minute_suffix(params)}", params
    )


@register_template("risultati.infortunio", 2)
def _render_risultati_infortunio_v2(params: NotificationParams) -> NotificationContent:
    return _live_content_v2(
        f"Infortunio per {_player(params)}",
        " · controlla la formazione",
        params,
        deep_link="/formazione",
    )


@register_template("risultati.squalifica", 2)
def _render_risultati_squalifica_v2(params: NotificationParams) -> NotificationContent:
    return _live_content_v2(
        f"{_player(params)} squalificato", " · non schierarlo", params, deep_link="/formazione"
    )


def _credits(value: object) -> str:
    return f"{value} cr." if value else ""


def _names(value: object) -> str:
    if isinstance(value, list):
        return " + ".join(str(name) for name in value)
    return ""


_TRADE_V2_TITLES: dict[str, str] = {
    "proposed": "{team} ti propone uno scambio",
    "accepted": "{team} ha accettato lo scambio",
    "rejected": "{team} ha rifiutato lo scambio",
    "countered": "{team} ti ha fatto una controproposta",
    "pending_approval": "Scambio con {team} in attesa dell'amministratore",
    "executed": "Scambio con {team} approvato",
    "rejected_by_admin": "Scambio con {team} rifiutato dall'amministratore",
}


@register_template("mercato.scambio", 2)
def _render_mercato_scambio_v2(params: NotificationParams) -> NotificationContent:
    status = str(params.get("status"))
    team = str(params.get("other_team", "Un altro fantallenatore"))
    title = _TRADE_V2_TITLES.get(status, "Aggiornamento scambio").format(team=team)
    gives = _join(_names(params.get("offered")), _credits(params.get("offered_credits")), sep=" + ")
    asks = _join(
        _names(params.get("requested")), _credits(params.get("requested_credits")), sep=" + "
    )
    # «offered» è ciò che dà chi ha proposto: per chi riceve è ciò che riceve.
    body = _join(
        f"Offre {gives}" if gives else "",
        f"chiede {asks}" if asks else "",
        f"scade {params['expires_label']}"
        if status == "proposed" and params.get("expires_label")
        else "",
    )
    return NotificationContent(
        title=title,
        body=body or "Apri Scambi per i dettagli.",
        deep_link="/mercato",
    )
