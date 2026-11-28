"""Assenze «in dubbio» dalla formazione probabile (1.5, Rosario 28/11).

Il fornitore dà gli assenti con uno stato: «Doubtful», «Questionable», «Day to day»… vuol
dire che il giocatore può giocare. Prima finiva tra gli indisponibili (grigio) come un
infortunato; ora il campo nuovo ``doubtful`` lo distingue, mentre ``hint`` e ``absence``
restano quelli di prima per l'app 1.4 già installata.
"""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from fantasy_turns.live_service import _unavailable_payload
from leagues.h2h_matchday_service import _player_score_response
from sports_data.predicted.models import PredictedLineupPlayer
from sports_data.predicted.read import (
    AthleteProbable,
    PredictedUnavailable,
    PredictedView,
    _hint_for,
    is_doubtful_absence,
)


@pytest.mark.parametrize(
    ("kind", "label"),
    [
        # FotMob: lo stato sta nel rientro previsto, il tipo resta «injury».
        ("injury", "Doubtful"),
        # Soccer-Oracle / API-Sports: lo stato è il tipo.
        ("doubtful", None),
        ("Questionable", None),
        ("uncertain", "Late December"),
        ("injury", "Day-to-day"),
        ("other", "day_to_day"),
        ("injury", "50-50"),
        ("injury", "In doubt"),
        (None, "In dubbio"),
        (None, "Da valutare"),
    ],
)
def test_provider_doubt_states_are_doubtful(kind: str | None, label: str | None) -> None:
    assert is_doubtful_absence(kind, label, blocked=False) is True


@pytest.mark.parametrize(
    ("kind", "label", "blocked"),
    [
        # Infortunato con rientro noto: assente certo.
        ("injury", "Mid December 2026", True),
        ("injury", None, False),
        # Squalificato o espulso: certo anche se il testo dice altro.
        ("suspension", "Doubtful", False),
        ("red_card", None, False),
        (None, "Squalificato", False),
        # Altro motivo (nazionale, motivi personali): non è un dubbio.
        ("other", "International duty", True),
        (None, None, False),
        # Bloccato dalla sincronizzazione: assenza certa già collegata alla rosa.
        ("doubtful", "Doubtful", True),
        # «doubt» solo come parola intera: «undoubtedly» non conta.
        ("injury", "Undoubtedly out", True),
    ],
)
def test_certain_absences_are_not_doubtful(
    kind: str | None, label: str | None, blocked: bool
) -> None:
    assert is_doubtful_absence(kind, label, blocked=blocked) is False


def _absent(kind: str | None, label: str | None, *, blocked: bool) -> PredictedLineupPlayer:
    return PredictedLineupPlayer(
        snapshot_id=uuid4(),
        athlete_id=uuid4(),
        side="home",
        display_name="Giocatore",
        is_starter=False,
        is_unavailable=True,
        unavailability_type=kind,
        unavailability_label=label,
        blocks_selection=blocked,
        sort_order=1,
    )


def test_hint_keeps_old_values_and_adds_the_doubt() -> None:
    """Classificatore completo: in dubbio vs infortunato vs squalificato vs altro.

    ``hint``/``absence``/``blocked`` sono identici a prima (compatibilità con l'app 1.4);
    cambia solo il campo nuovo ``doubtful``.
    """
    doubtful = _hint_for(_absent("injury", "Doubtful", blocked=False))
    injured = _hint_for(_absent("injury", "Mid December 2026", blocked=True))
    suspended = _hint_for(_absent("suspension", None, blocked=True))
    other = _hint_for(_absent("other", "International duty", blocked=True))
    assert doubtful is not None and injured is not None
    assert suspended is not None and other is not None

    assert (doubtful.hint, doubtful.absence, doubtful.blocked) == ("unavailable", "injured", False)
    assert doubtful.doubtful is True
    assert doubtful.note == "Doubtful"

    assert (injured.hint, injured.absence, injured.blocked) == ("unavailable", "injured", True)
    assert injured.doubtful is False
    assert (suspended.hint, suspended.absence, suspended.note) == (
        "unavailable",
        "suspended",
        "Squalificato",
    )
    assert suspended.doubtful is False
    assert (other.hint, other.absence) == ("unavailable", "other")
    assert other.doubtful is False


def test_starters_and_bench_are_never_doubtful() -> None:
    starter = PredictedLineupPlayer(
        snapshot_id=uuid4(),
        athlete_id=uuid4(),
        side="home",
        display_name="Titolare",
        is_starter=True,
        is_unavailable=False,
        blocks_selection=False,
        sort_order=1,
    )
    hint = _hint_for(starter)
    assert hint is not None
    assert hint.hint == "starter"
    assert hint.doubtful is False


def test_h2h_player_carries_the_doubt_without_touching_the_old_fields() -> None:
    """Dettaglio scontro: ``probableDoubt`` nuovo, ``probableHint``/``probableAbsence``
    invariati (l'app 1.4 continua a vederlo grigio)."""
    probable = AthleteProbable(
        hint="unavailable", note="Doubtful", blocked=False, absence="injured", doubtful=True
    )
    body = _player_score_response(
        athlete_id=uuid4(),
        name="Giocatore",
        photo_url=None,
        role="D",
        snapshot=None,
        probable=probable,
        is_effective_starter=True,
        is_bench=False,
    ).model_dump(by_alias=True)
    assert body["probableHint"] == "unavailable"
    assert body["probableAbsence"] == "injured"
    assert body["selectionBlocked"] is False
    assert body["probableDoubt"] is True

    plain = _player_score_response(
        athlete_id=uuid4(),
        name="Senza dato",
        photo_url=None,
        role="D",
        snapshot=None,
        probable=None,
        is_effective_starter=True,
        is_bench=False,
    ).model_dump(by_alias=True)
    assert plain["probableDoubt"] is False


def test_fixture_unavailable_list_carries_the_doubt() -> None:
    """Schermo «Partita»: l'elenco degli assenti dice chi è solo in dubbio."""
    view = PredictedView(
        home=None,
        away=None,
        unavailable=(
            PredictedUnavailable(
                athlete_id=None,
                name="Dubbio",
                side="home",
                kind="injury",
                label="Doubtful",
                blocks_selection=False,
                doubtful=True,
            ),
            PredictedUnavailable(
                athlete_id=None,
                name="Certo",
                side="away",
                kind="injury",
                label="Mid December",
                blocks_selection=True,
            ),
        ),
    )
    fixture = SimpleNamespace(
        home_club=SimpleNamespace(name="Casa"), away_club=SimpleNamespace(name="Ospiti")
    )
    rows = [row.model_dump(by_alias=True) for row in _unavailable_payload(view, fixture)]
    assert [(row["name"], row["probableDoubt"], row["blocksSelection"]) for row in rows] == [
        ("Dubbio", True, False),
        ("Certo", False, True),
    ]
    assert rows[0]["kind"] == "injury"
    assert rows[0]["label"] == "Doubtful"
