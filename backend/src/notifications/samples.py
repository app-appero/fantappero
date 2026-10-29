"""Notifiche di prova: un esempio per ogni tipo, per vedere testi, icone e push senza aspettare un evento."""

from __future__ import annotations

from dataclasses import dataclass

from database.enums import NotificationCategory


@dataclass(frozen=True)
class SampleNotification:
    key: str
    category: NotificationCategory
    template_key: str
    template_version: int
    params: dict[str, object]


_MATCH = {"fixture_label": "Inter–Juventus", "score_label": "1–0", "team_name": "La tua squadra"}

SAMPLES: tuple[SampleNotification, ...] = (
    SampleNotification(
        "gol",
        NotificationCategory.RISULTATI,
        "risultati.gol",
        2,
        {**_MATCH, "player": "Lautaro Martinez", "minute": 23},
    ),
    SampleNotification(
        "assist",
        NotificationCategory.RISULTATI,
        "risultati.assist",
        1,
        {**_MATCH, "player": "Dumfries", "scorer": "Lautaro Martinez", "minute": 23},
    ),
    SampleNotification(
        "ammonizione",
        NotificationCategory.RISULTATI,
        "risultati.ammonizione",
        1,
        {**_MATCH, "player": "Barella", "minute": 41},
    ),
    SampleNotification(
        "espulsione",
        NotificationCategory.RISULTATI,
        "risultati.espulsione",
        2,
        {**_MATCH, "player": "Bastoni", "minute": 61},
    ),
    SampleNotification(
        "sostituzione",
        NotificationCategory.RISULTATI,
        "risultati.sostituzione",
        1,
        {**_MATCH, "player_out": "Leao", "player_in": "Chiesa", "minute": 70},
    ),
    SampleNotification(
        "infortunio",
        NotificationCategory.RISULTATI,
        "risultati.infortunio",
        2,
        {"player": "Lookman", "team_name": "La tua squadra"},
    ),
    SampleNotification(
        "squalifica",
        NotificationCategory.RISULTATI,
        "risultati.squalifica",
        2,
        {"player": "Acerbi", "team_name": "La tua squadra"},
    ),
    SampleNotification(
        "scambio-proposta",
        NotificationCategory.MERCATO,
        "mercato.scambio",
        2,
        {
            "status": "proposed",
            "other_team": "Giulia United",
            "offered": ["Tonali"],
            "requested": ["Lookman"],
            "offered_credits": 5,
            "expires_label": "domani alle 20:00",
        },
    ),
    SampleNotification(
        "scambio-accettato",
        NotificationCategory.MERCATO,
        "mercato.scambio",
        2,
        {
            "status": "accepted",
            "other_team": "Giulia United",
            "offered": ["Tonali"],
            "requested": ["Lookman"],
        },
    ),
    SampleNotification(
        "asta-sorpasso",
        NotificationCategory.MERCATO,
        "mercato.asta_live_sorpassato",
        1,
        {"athlete_name": "Y. Diouf"},
    ),
    SampleNotification(
        "formazione",
        NotificationCategory.FORMAZIONE,
        "formazione.scadenza_turno",
        1,
        {"round_number": 8, "cutoff_local": "20:45"},
    ),
    SampleNotification(
        "formazione-blocco",
        NotificationCategory.FORMAZIONE,
        "formazione.blocco_imminente",
        1,
        {"round_number": 8, "kickoff_local": "20:45", "player_count": 3},
    ),
    SampleNotification(
        "turno",
        NotificationCategory.RISULTATI,
        "risultati.omologazione",
        1,
        {"round_number": 7},
    ),
)
