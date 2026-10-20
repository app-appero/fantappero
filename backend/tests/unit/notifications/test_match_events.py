"""Notifiche live: gol, espulsioni, infortuni — solo ai proprietari del giocatore."""

from __future__ import annotations

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
    assert call["params"] == {"minute": 63, "player": "Mario Rossi"}
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
