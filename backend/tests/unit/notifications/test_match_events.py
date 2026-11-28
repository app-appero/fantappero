"""Notifiche live: gol, espulsioni, infortuni — solo ai proprietari del giocatore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from notifications import match_events


class _FakeService:
    calls: list[dict[str, object]] = []

    def __init__(self, session: object) -> None:
        pass

    def create_notification(self, **kwargs: object) -> tuple[None, bool]:
        _FakeService.calls.append(kwargs)
        return None, True


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    _FakeService.calls = []
    owner = uuid4()
    monkeypatch.setattr(match_events, "NotificationService", _FakeService)
    monkeypatch.setattr(match_events, "user_ids_for_teams", lambda s, ids: {uuid4(): owner})
    return [owner]


def _session() -> MagicMock:
    session = MagicMock()
    session.get.return_value = SimpleNamespace(canonical_name="Mario Rossi")
    session.scalars.return_value.all.return_value = [uuid4()]
    return session


def _event(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "id": uuid4(),
        "athlete_id": uuid4(),
        "scoring_kind": None,
        "event_type": "Goal",
        "event_detail": None,
        "minute_elapsed": 63,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_goal_notifies_owner_during_live_match() -> None:
    sent = match_events.notify_match_event(
        _session(), event=_event(scoring_kind="goal"), fixture_status="2H"
    )
    assert sent == 1
    call = _FakeService.calls[0]
    assert call["template_key"] == "risultati.gol"
    # "deep_link" è sempre presente (TASK4): col session finto non si risolve
    # nessuno scontro, quindi ricade sul percorso generico "/turni".
    assert call["params"] == {"minute": 63, "player": "Mario Rossi", "deep_link": "/turni"}
    assert call["template_version"] == 2


def test_red_card_notifies_owner() -> None:
    event = _event(event_type="Card", event_detail="Red Card")
    assert match_events.notify_match_event(_session(), event=event, fixture_status="1H") == 1
    assert _FakeService.calls[0]["template_key"] == "risultati.espulsione"


def test_yellow_card_notifies_owner() -> None:
    yellow = _event(event_type="Card", event_detail="Yellow Card")
    assert match_events.notify_match_event(_session(), event=yellow, fixture_status="1H") == 1
    assert _FakeService.calls[0]["template_key"] == "risultati.ammonizione"


def test_second_yellow_counts_as_red() -> None:
    event = _event(event_type="Card", event_detail="Second Yellow card")
    assert match_events.notify_match_event(_session(), event=event, fixture_status="2H") == 1
    assert _FakeService.calls[0]["template_key"] == "risultati.espulsione"


def test_own_goal_is_ignored() -> None:
    own = _event(scoring_kind="own_goal")
    assert match_events.notify_match_event(_session(), event=own, fixture_status="1H") == 0
    assert _FakeService.calls == []


def test_goal_with_assist_notifies_the_assist_owner_too() -> None:
    event = _event(scoring_kind="goal", related_athlete_id=uuid4())
    assert match_events.notify_match_event(_session(), event=event, fixture_status="2H") == 2
    keys = [call["template_key"] for call in _FakeService.calls]
    assert keys == ["risultati.gol", "risultati.assist"]


def test_substitution_notifies_owners_of_both_players() -> None:
    event = _event(event_type="subst", related_athlete_id=uuid4())
    assert match_events.notify_match_event(_session(), event=event, fixture_status="2H") == 2
    assert {call["template_key"] for call in _FakeService.calls} == {"risultati.sostituzione"}


class _DedupService(_FakeService):
    """Come il servizio vero: una seconda notifica con la stessa chiave non viene creata."""

    def create_notification(self, **kwargs: object) -> tuple[None, bool]:
        key = (kwargs["user_id"], kwargs["dedup_key"])
        if any((call["user_id"], call["dedup_key"]) == key for call in _FakeService.calls):
            return None, False
        _FakeService.calls.append(kwargs)
        return None, True


def test_substitution_is_notified_once_with_a_stable_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QA 20-21/11: la stessa sostituzione arrivava due volte. Chi ha in rosa sia chi esce sia
    chi entra riceveva due avvisi (una chiave per giocatore), e il provider che corregge minuto
    o dettaglio crea una nuova riga evento (un nuovo id): la chiave ora è partita + chi esce."""
    owner = uuid4()
    team = uuid4()
    monkeypatch.setattr(match_events, "NotificationService", _DedupService)
    monkeypatch.setattr(match_events, "user_ids_for_teams", lambda s, ids: {team: owner})
    fixture_id = uuid4()
    leaving = uuid4()
    entering = uuid4()

    first = _event(
        event_type="subst",
        event_detail="Substitution 2",
        athlete_id=leaving,
        related_athlete_id=entering,
        fixture_id=fixture_id,
    )
    # Stessa squadra proprietaria di entrambi: un solo avviso.
    assert match_events.notify_match_event(_session(), event=first, fixture_status="2H") == 1

    # Il provider rinumera la sostituzione e corregge il minuto: nuova riga, stesso cambio.
    corrected = _event(
        event_type="subst",
        event_detail="Substitution 3",
        minute_elapsed=64,
        athlete_id=leaving,
        related_athlete_id=entering,
        fixture_id=fixture_id,
    )
    assert match_events.notify_match_event(_session(), event=corrected, fixture_status="2H") == 0
    assert len(_FakeService.calls) == 1
    assert _FakeService.calls[0]["dedup_key"] == (
        f"match_event_subst:{fixture_id}:{leaving}:{owner}:{team}"
    )


def test_finished_match_does_not_notify_backfill() -> None:
    event = _event(scoring_kind="goal")
    assert match_events.notify_match_event(_session(), event=event, fixture_status="FT") == 0


def test_event_without_athlete_is_ignored() -> None:
    event = _event(scoring_kind="goal", athlete_id=None)
    assert match_events.notify_match_event(_session(), event=event, fixture_status="1H") == 0


def test_failure_never_propagates() -> None:
    session = _session()
    session.get.side_effect = RuntimeError("boom")
    event = _event(scoring_kind="goal")
    assert match_events.notify_match_event(session, event=event, fixture_status="1H") == 0


def test_availability_injury_and_suspension() -> None:
    for value, key in (("injury", "risultati.infortunio"), ("suspension", "risultati.squalifica")):
        _FakeService.calls = []
        row = SimpleNamespace(id=uuid4(), athlete_id=uuid4(), category=SimpleNamespace(value=value))
        assert match_events.notify_availability(_session(), availability=row) == 1
        assert _FakeService.calls[0]["template_key"] == key


def test_availability_other_category_ignored() -> None:
    row = SimpleNamespace(id=uuid4(), athlete_id=uuid4(), category=SimpleNamespace(value="other"))
    assert match_events.notify_availability(_session(), availability=row) == 0


# -- TASK4: deep link allo scontro H2H specifico -----------------------------------------------


def test_goal_resolves_deep_link_per_recipient_team(monkeypatch: pytest.MonkeyPatch) -> None:
    """La risoluzione del deep link è chiamata con la fixture dell'evento e il
    team del destinatario (non una volta sola per l'evento): squadre diverse
    possono finire in scontri H2H diversi."""
    fixture_id = uuid4()
    seen_calls: list[dict[str, object]] = []

    def fake_resolve(session: object, *, team_id: object, fixture_id: object, fallback: str) -> str:
        seen_calls.append({"team_id": team_id, "fixture_id": fixture_id, "fallback": fallback})
        return f"/turni/scontro/{team_id}"

    monkeypatch.setattr(match_events, "resolve_matchup_deep_link", fake_resolve)
    event = _event(scoring_kind="goal", fixture_id=fixture_id)
    assert match_events.notify_match_event(_session(), event=event, fixture_status="2H") == 1

    assert len(seen_calls) == 1
    assert seen_calls[0]["fixture_id"] == fixture_id
    assert seen_calls[0]["fallback"] == "/turni"
    call_params = _FakeService.calls[0]["params"]
    assert call_params["deep_link"] == f"/turni/scontro/{seen_calls[0]['team_id']}"


# -- «Gol annullato» / «Assist annullato» (Rosario 28/11) --------------------------------------


def _fixture(status: str = "2H", hours_since_kickoff: float | None = 1.0) -> SimpleNamespace:
    kickoff = (
        None
        if hours_since_kickoff is None
        else datetime.now(UTC) - timedelta(hours=hours_since_kickoff)
    )
    return SimpleNamespace(status_short=status, kickoff_at=kickoff)


@pytest.fixture
def original_filters(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Il filtro «chi ha ricevuto l'originale» e quello sul turno omologato, finti: passano
    tutti i proprietari. Ritorna i prefissi dei codici delle notifiche originali cercate."""
    prefixes: list[str] = []

    def fake_originals(session: object, owners: dict, prefix: str) -> dict:
        prefixes.append(prefix)
        return owners

    monkeypatch.setattr(match_events, "_owners_with_original", fake_originals)
    monkeypatch.setattr(match_events, "_round_homologated", lambda session, **kwargs: False)
    return prefixes


def _retracted_goal(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "scoring_kind": "goal",
        "club": SimpleNamespace(name="Inter"),
        "fixture_id": uuid4(),
        **overrides,
    }
    return _event(**values)


def test_retracted_goal_notifies_only_who_got_the_original(original_filters: list[str]) -> None:
    event = _retracted_goal()
    sent = match_events.notify_match_event_retracted(
        _session(), event=event, fixture=_fixture(), reason="fuorigioco"
    )
    assert sent == 1
    call = _FakeService.calls[0]
    assert call["template_key"] == "risultati.gol_annullato"
    assert call["template_version"] == 1
    assert call["category"] == match_events.NotificationCategory.RISULTATI
    assert call["params"]["reason"] == "fuorigioco"
    assert call["params"]["club_name"] == "Inter"
    assert call["params"]["player"] == "Mario Rossi"
    assert call["params"]["deep_link"] == "/turni"
    # Nuovo codice anti-duplicato, e l'originale cercata con quello del «Gol di…».
    assert str(call["dedup_key"]).startswith(f"match_event_retracted:{event.id}:")
    assert original_filters == [f"match_event:{event.id}"]


def test_retracted_goal_without_a_known_reason_sends_no_reason(
    original_filters: list[str],
) -> None:
    sent = match_events.notify_match_event_retracted(
        _session(), event=_retracted_goal(), fixture=_fixture()
    )
    assert sent == 1
    assert "reason" not in _FakeService.calls[0]["params"]


def test_retracted_goal_with_assist_notifies_the_assist_owner_too(
    original_filters: list[str],
) -> None:
    event = _retracted_goal(related_athlete_id=uuid4())
    sent = match_events.notify_match_event_retracted(
        _session(), event=event, fixture=_fixture(), reason="fallo di mano"
    )
    assert sent == 2
    goal, assist = _FakeService.calls
    assert goal["template_key"] == "risultati.gol_annullato"
    assert assist["template_key"] == "risultati.assist_annullato"
    assert assist["params"]["scorer"] == "Mario Rossi"
    assert assist["params"]["reason"] == "fallo di mano"
    # Codici diversi per gol e assist: chi ha entrambi riceve entrambi gli avvisi, come prima.
    assert str(goal["dedup_key"]).startswith(f"match_event_retracted:{event.id}:")
    assert str(assist["dedup_key"]).startswith(f"match_event_retracted_assist:{event.id}:")
    assert original_filters == [f"match_event:{event.id}", f"match_event_assist:{event.id}"]


def test_goal_only_corrected_by_the_provider_is_not_announced_as_cancelled(
    original_filters: list[str],
) -> None:
    """Minuto o assist corretti dal fornitore: la riga cambia chiave ma il gol c'è ancora."""
    event = _retracted_goal(related_athlete_id=uuid4())
    sent = match_events.notify_match_event_retracted(
        _session(), event=event, fixture=_fixture(), goal_still_valid=True
    )
    assert sent == 1
    assert _FakeService.calls[0]["template_key"] == "risultati.assist_annullato"

    _FakeService.calls = []
    sent = match_events.notify_match_event_retracted(
        _session(),
        event=event,
        fixture=_fixture(),
        goal_still_valid=True,
        assist_still_valid=True,
    )
    assert sent == 0
    assert _FakeService.calls == []


def test_retracted_goal_is_sent_once_even_if_it_is_retracted_again(
    monkeypatch: pytest.MonkeyPatch, original_filters: list[str]
) -> None:
    """Il gol torna valido e viene annullato di nuovo: stesso evento, stesso codice, nessun
    secondo avviso (limite documentato)."""
    monkeypatch.setattr(match_events, "NotificationService", _DedupService)
    owner = uuid4()
    team = uuid4()
    monkeypatch.setattr(match_events, "user_ids_for_teams", lambda s, ids: {team: owner})
    event = _retracted_goal()
    first = match_events.notify_match_event_retracted(_session(), event=event, fixture=_fixture())
    again = match_events.notify_match_event_retracted(_session(), event=event, fixture=_fixture())
    assert (first, again) == (1, 0)
    assert len(_FakeService.calls) == 1
    assert _FakeService.calls[0]["dedup_key"] == f"match_event_retracted:{event.id}:{owner}:{team}"


@pytest.mark.parametrize(
    "fixture",
    [
        _fixture(status="NS"),
        _fixture(status="PST"),
        _fixture(status="CANC"),
        _fixture(status="FT", hours_since_kickoff=30),
        _fixture(status="2H", hours_since_kickoff=None),
    ],
    ids=["non iniziata", "rinviata", "annullata", "finita da più di un giorno", "senza orario"],
)
def test_retraction_is_not_notified_for_old_or_not_played_matches(
    original_filters: list[str], fixture: SimpleNamespace
) -> None:
    sent = match_events.notify_match_event_retracted(
        _session(), event=_retracted_goal(related_athlete_id=uuid4()), fixture=fixture
    )
    assert sent == 0
    assert _FakeService.calls == []


@pytest.mark.parametrize("status", ["1H", "HT", "2H", "ET", "P", "FT", "AET", "PEN"])
def test_retraction_is_notified_while_live_and_just_after_the_end(
    original_filters: list[str], status: str
) -> None:
    sent = match_events.notify_match_event_retracted(
        _session(), event=_retracted_goal(), fixture=_fixture(status=status, hours_since_kickoff=3)
    )
    assert sent == 1


@pytest.mark.parametrize("scoring_kind", ["assist", "own_goal", "penalty_missed", None])
def test_only_goals_and_scored_penalties_have_a_retraction_notification(
    original_filters: list[str], scoring_kind: str | None
) -> None:
    event = _retracted_goal(scoring_kind=scoring_kind, related_athlete_id=uuid4())
    assert (
        match_events.notify_match_event_retracted(_session(), event=event, fixture=_fixture()) == 0
    )
    assert _FakeService.calls == []


def test_retracted_scored_penalty_is_notified_as_a_goal(original_filters: list[str]) -> None:
    event = _retracted_goal(scoring_kind="penalty_scored")
    assert (
        match_events.notify_match_event_retracted(_session(), event=event, fixture=_fixture()) == 1
    )
    assert _FakeService.calls[0]["template_key"] == "risultati.gol_annullato"


def test_retraction_without_original_notification_sends_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nessuno aveva ricevuto «Gol di…» (partita già finita all'arrivo del gol, interruttore
    spento, giocatore preso dopo): nessun avviso di annullamento."""
    monkeypatch.setattr(match_events, "_owners_with_original", lambda session, owners, prefix: {})
    monkeypatch.setattr(match_events, "_round_homologated", lambda session, **kwargs: False)
    event = _retracted_goal(related_athlete_id=uuid4())
    assert (
        match_events.notify_match_event_retracted(_session(), event=event, fixture=_fixture()) == 0
    )
    assert _FakeService.calls == []


def test_retraction_is_not_sent_to_a_team_whose_round_is_already_homologated(
    monkeypatch: pytest.MonkeyPatch, original_filters: list[str]
) -> None:
    monkeypatch.setattr(match_events, "_round_homologated", lambda session, **kwargs: True)
    event = _retracted_goal()
    assert (
        match_events.notify_match_event_retracted(_session(), event=event, fixture=_fixture()) == 0
    )
    assert _FakeService.calls == []


def test_retraction_failure_never_propagates(original_filters: list[str]) -> None:
    session = _session()
    session.get.side_effect = RuntimeError("boom")
    event = _retracted_goal()
    assert match_events.notify_match_event_retracted(session, event=event, fixture=_fixture()) == 0


def test_availability_resolves_deep_link_with_formation_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Infortunio/squalifica: se la fixture non porta a nessuno scontro si
    torna su «/formazione» (non «/turni»): è il posto giusto da cui togliere
    il giocatore, coerente col comportamento preesistente dei template v2."""
    fixture_id = uuid4()
    seen_fallbacks: list[str] = []

    def fake_resolve(session: object, *, team_id: object, fixture_id: object, fallback: str) -> str:
        seen_fallbacks.append(fallback)
        return fallback

    monkeypatch.setattr(match_events, "resolve_matchup_deep_link", fake_resolve)
    row = SimpleNamespace(
        id=uuid4(),
        athlete_id=uuid4(),
        category=SimpleNamespace(value="injury"),
        fixture_id=fixture_id,
    )
    assert match_events.notify_availability(_session(), availability=row) == 1
    assert seen_fallbacks == ["/formazione"]
