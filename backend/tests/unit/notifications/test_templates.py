"""Unit tests for the versioned notification template registry (EP09-01)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest

from notifications.templates import _TEMPLATES, render_notification


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


def test_render_mercato_esito_busta_lost_on_repeated_tiebreak_tie() -> None:
    """Spareggio di nuovo in parità: chi perde non ha offerto meno, è arrivato dopo."""
    content = render_notification(
        "mercato.esito_busta",
        1,
        {"outcome": "lost", "athlete_name": "Bomber", "lost_on_tie": True},
    )
    assert content.title == "Busta non aggiudicata"
    assert content.body == (
        "Non hai aggiudicato Bomber: a parità d'importo nello spareggio vince "
        "l'offerta inviata per prima."
    )
    assert "inferiore" not in content.body


def test_render_mercato_esito_busta_waiver_has_own_titles_and_link() -> None:
    """QA 19-20/11: gli esiti degli svincolati arrivavano con i titoli e il link dell'asta."""
    base = {
        "athlete_name": "Bomber",
        "league_id": "abc",
        "league_name": "Lega Test",
        "session_kind": "waiver",
    }
    assigned = render_notification(
        "mercato.esito_busta", 1, {**base, "outcome": "assigned", "amount_credits": 42}
    )
    assert assigned.title == "Svincolato aggiudicato"
    assert assigned.body == "«Lega Test» · Hai aggiudicato Bomber dagli svincolati per 42 crediti."
    assert assigned.deep_link == "/svincolati?lega=abc"

    lost = render_notification("mercato.esito_busta", 1, {**base, "outcome": "lost"})
    assert lost.title == "Svincolato perso"
    assert lost.body == (
        "«Lega Test» · Non hai aggiudicato Bomber dagli svincolati: offerta inferiore."
    )
    assert lost.deep_link == "/svincolati?lega=abc"

    not_assignable = render_notification(
        "mercato.esito_busta", 1, {**base, "outcome": "lost", "not_assignable": True}
    )
    assert not_assignable.title == "Svincolato perso"
    assert "giocatore da svincolare non più in rosa" in not_assignable.body

    lost_on_tie = render_notification(
        "mercato.esito_busta", 1, {**base, "outcome": "lost", "lost_on_tie": True}
    )
    assert lost_on_tie.title == "Svincolato perso"
    assert "vince l'offerta inviata per prima" in lost_on_tie.body

    tiebreak = render_notification("mercato.esito_busta", 1, {**base, "outcome": "tiebreak"})
    assert tiebreak.title == "Spareggio svincolati aperto"
    assert tiebreak.body == (
        "«Lega Test» · Parità su Bomber negli svincolati: sei ammesso allo spareggio, "
        "hai 24 ore per rilanciare."
    )
    assert tiebreak.deep_link == "/svincolati?lega=abc"

    cancelled = render_notification(
        "mercato.esito_busta", 1, {**base, "outcome": "lost", "tiebreak_cancelled": True}
    )
    assert cancelled.title == "Spareggio svincolati annullato"
    assert cancelled.body == (
        "«Lega Test» · Lo spareggio degli svincolati su Bomber è annullato: "
        "il calciatore non è più disponibile."
    )
    assert cancelled.deep_link == "/svincolati?lega=abc"

    for content in (assigned, lost, not_assignable, lost_on_tie, tiebreak, cancelled):
        assert "Busta" not in content.title
        assert "/asta" not in (content.deep_link or "")


def test_render_mercato_esito_busta_sealed_bid_unchanged() -> None:
    """L'asta a buste (con o senza ``session_kind``) mantiene titoli e link di prima."""
    for extra in ({}, {"session_kind": "initial_auction"}):
        content = render_notification(
            "mercato.esito_busta",
            1,
            {
                "outcome": "assigned",
                "athlete_name": "Bomber",
                "amount_credits": 42,
                "league_id": "abc",
                **extra,
            },
        )
        assert content.title == "Busta aggiudicata"
        assert content.deep_link == "/asta?lega=abc"


def test_render_mercato_asta_live_perso_variants() -> None:
    """P4: capofila senza crediti (o senza posto) alla chiusura del lotto live."""
    base = {"athlete_name": "Bomber", "amount_credits": 500, "league_id": "abc"}
    credits = render_notification(
        "mercato.asta_live_perso", 1, {**base, "reason": "insufficient_credits", "reassigned": True}
    )
    assert credits.title == "Lotto perso: crediti insufficienti"
    assert "Bomber" in credits.body and "500 crediti" in credits.body
    assert "offerta successiva" in credits.body
    assert credits.deep_link == "/asta-live?lega=abc"

    passed = render_notification(
        "mercato.asta_live_perso",
        1,
        {**base, "reason": "insufficient_credits", "reassigned": False},
    )
    assert passed.title == "Lotto perso: crediti insufficienti"
    assert "svincolato" in passed.body

    roster = render_notification(
        "mercato.asta_live_perso", 1, {**base, "reason": "assignment_failed", "reassigned": True}
    )
    assert roster.title == "Lotto perso: rosa al completo"
    assert "500" not in roster.body


def test_render_mercato_asta_live_perso_after_declined_or_unchosen_swap() -> None:
    """Rosa al completo e scambio rifiutato, o non scelto prima della fine della sessione."""
    base = {"athlete_name": "Bomber", "amount_credits": 500}
    declined = render_notification(
        "mercato.asta_live_perso", 1, {**base, "reason": "swap_declined", "reassigned": True}
    )
    assert declined.title == "Lotto perso: rosa al completo"
    assert declined.body == (
        "Hai rinunciato allo scambio per Bomber con la rosa al completo: "
        "il calciatore va all'offerta successiva."
    )
    ended = render_notification(
        "mercato.asta_live_perso", 1, {**base, "reason": "session_ended", "reassigned": False}
    )
    assert ended.title == "Lotto perso: rosa al completo"
    assert ended.body == (
        "L'asta è terminata prima che scegliessi chi scambiare con Bomber: "
        "nessun'altra offerta valida, il calciatore resta svincolato."
    )


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


def test_render_lega_eliminata_names_who_deleted_the_league() -> None:
    """QA 19/11: l'eliminazione da parte dell'amministratore di lega ha un testo suo."""
    by_operator = render_notification("lega.eliminata", 1, {"league_name": "Lega Amici"})
    assert by_operator.title == "Lega eliminata"
    assert by_operator.body == "La lega Lega Amici è stata eliminata dall'amministrazione."
    assert by_operator.deep_link == "/"

    by_admin = render_notification(
        "lega.eliminata", 1, {"league_name": "Lega Amici", "by_league_admin": True}
    )
    assert by_admin.title == "Lega eliminata"
    assert by_admin.body == "La lega Lega Amici è stata eliminata dall'amministratore della lega."
    assert by_admin.deep_link == "/"

    nameless = render_notification("lega.eliminata", 1, {"by_league_admin": True})
    assert nameless.body == "Una tua lega è stata eliminata dall'amministratore della lega."
    operator_nameless = render_notification("lega.eliminata", 1, {})
    assert operator_nameless.body == "Una tua lega è stata eliminata dall'amministrazione."


def test_render_lega_al_completo_points_the_admin_to_the_league_admin_page() -> None:
    """Decisione del 20/11: a lega al completo l'amministratore apre il mercato."""
    content = render_notification(
        "lega.al_completo", 1, {"league_name": "Lega Amici", "league_id": "abc-123"}
    )
    assert content.title == "La lega è al completo: puoi aprire il mercato"
    assert content.body == (
        "«Lega Amici» · Tutti i posti sono occupati. Apri il mercato da Amministrazione lega."
    )
    assert content.deep_link == "/lega/amministrazione?lega=abc-123"


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


def test_goal_v2_uses_matchup_deep_link_when_resolved() -> None:
    """TASK4: se il produttore ha risolto lo scontro H2H del destinatario,
    il link specifico vince sul generico "/turni"."""
    content = render_notification(
        "risultati.gol",
        2,
        {"player": "Lautaro Martinez", "minute": 23, "deep_link": "/turni/scontro/abc-123"},
    )
    assert content.deep_link == "/turni/scontro/abc-123"


def test_infortunio_v2_defaults_to_formazione_without_matchup() -> None:
    content = render_notification("risultati.infortunio", 2, {"player": "Lookman"})
    assert content.deep_link == "/formazione"


def test_infortunio_v2_uses_matchup_deep_link_when_resolved() -> None:
    content = render_notification(
        "risultati.infortunio",
        2,
        {"player": "Lookman", "deep_link": "/turni/scontro/xyz-999"},
    )
    assert content.deep_link == "/turni/scontro/xyz-999"


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


def test_render_formazione_blocco_imminente_singular() -> None:
    content = render_notification(
        "formazione.blocco_imminente",
        1,
        {"round_number": 8, "kickoff_local": "20:45", "player_count": 1},
    )
    assert content.title == "Blocco formazione in arrivo"
    assert "1 calciatore" in content.body
    assert "si blocca " in content.body  # singolare, non "si bloccano"
    assert "il suo turno" in content.body
    assert "20:45" in content.body
    assert content.deep_link == "/formazione"


def test_render_formazione_blocco_imminente_plural() -> None:
    content = render_notification(
        "formazione.blocco_imminente",
        1,
        {"round_number": 8, "kickoff_local": "18:00", "player_count": 4},
    )
    assert "4 calciatori" in content.body
    assert "si bloccano" in content.body
    assert "il loro turno" in content.body


def test_render_formazione_scadenza_turno_v2_says_the_lock_time() -> None:
    """QA 20-21/11: il promemoria dice quando si blocca la formazione, non il calcio d'inizio."""
    content = render_notification(
        "formazione.scadenza_turno",
        2,
        {"round_number": 11, "lock_local": "20/11/2026 20:45", "league_name": "Lega Demo"},
    )
    assert content.title == "Scadenza formazione in arrivo"
    assert content.body == (
        "«Lega Demo» · Turno 11: la formazione si blocca alle 20/11/2026 20:45. "
        "Salvala prima del blocco."
    )
    assert "chiude" not in content.body
    assert "fischio d'inizio" not in content.body


def test_render_formazione_blocco_imminente_v2_counts_roster_players() -> None:
    plural = render_notification(
        "formazione.blocco_imminente",
        2,
        {
            "round_number": 11,
            "lock_local": "20/11/2026 20:45",
            "kickoff_time": "21:00",
            "player_count": 3,
        },
    )
    assert plural.title == "Blocco formazione in arrivo"
    assert plural.body == (
        "3 calciatori della tua rosa si bloccano alle 20/11/2026 20:45: "
        "la loro partita inizia alle 21:00."
    )
    single = render_notification(
        "formazione.blocco_imminente",
        2,
        {"lock_local": "20/11/2026 20:45", "kickoff_time": "21:00", "player_count": 1},
    )
    assert single.body == (
        "1 calciatore della tua rosa si blocca alle 20/11/2026 20:45: "
        "la sua partita inizia alle 21:00."
    )
    # Margine di lega 0: blocco e calcio d'inizio coincidono.
    same_time = render_notification(
        "formazione.blocco_imminente",
        2,
        {"lock_local": "20/11/2026 21:00", "kickoff_time": "21:00", "player_count": 2},
    )
    assert same_time.body == (
        "2 calciatori della tua rosa si bloccano alle 20/11/2026 21:00, "
        "al calcio d'inizio della loro partita."
    )
    assert single.deep_link == "/formazione"


# Notifiche che non riguardano una lega dell'utente: avvisi generici e degli operatori,
# segnalazioni, invito non ancora accettato (il destinatario non è nella lega) e lega eliminata.
_NOT_LEAGUE_SCOPED = {
    "sistema.generico",
    "sistema.invito_lega",
    "sistema.richiesta_tester",
    "sistema.feedback_utente",
    "sistema.feedback_stato",
    "lega.eliminata",
}


def test_every_league_notification_links_its_league() -> None:
    """Chi è in più leghe apre la notifica nella lega dell'evento (Rosario 21/11).

    Il sito e l'app leggono la lega dal ``?lega=`` del deep link, che è anche il ``deepLink``
    dei dati della push: ogni template di lega, in ogni sua variante, deve metterlo.
    """
    base: dict[str, object] = {
        "league_id": "lega-x",
        "league_name": "Lega X",
        "proposal_id": "p-1",
        "deep_link": "/turni/scontro/slot-1",
    }
    variants: list[dict[str, object]] = [
        {},
        {"outcome": "accepted"},
        {"outcome": "assigned"},
        {"outcome": "tiebreak"},
        {"tiebreak_cancelled": True},
        {"session_kind": "waiver"},
        {"session_kind": "waiver", "outcome": "assigned"},
        {"status": "proposed"},
    ]
    league_scoped = sorted(key for key in _TEMPLATES if key[0] not in _NOT_LEAGUE_SCOPED)
    assert len(league_scoped) > 20
    for template_key, version in league_scoped:
        for variant in variants:
            content = render_notification(template_key, version, {**base, **variant})
            assert content.deep_link is not None, (template_key, version, variant)
            query = parse_qs(urlsplit(content.deep_link).query)
            assert query.get("lega") == ["lega-x"], (template_key, version, content.deep_link)


def test_every_test_sample_renders() -> None:
    from notifications.samples import SAMPLES

    keys = [s.key for s in SAMPLES]
    assert len(keys) == len(set(keys))
    for sample in SAMPLES:
        content = render_notification(sample.template_key, sample.template_version, sample.params)
        assert content.title
        assert content.body
