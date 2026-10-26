"""Deep link allo scontro H2H preciso per le notifiche di evento calciatore (TASK4).

Nessun DB reale: la catena lega -> turno -> giornata H2H -> scontro viene
simulata con un ``session`` finto i cui ``get``/``scalar`` rispondono in
sequenza, stesso approccio delle altre suite unit di questo modulo
(``test_match_events.py``).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from notifications import matchup_links
from notifications.matchup_links import matchup_deep_link, resolve_matchup_deep_link


def test_matchup_deep_link_format() -> None:
    slot_id = uuid4()
    assert matchup_deep_link(slot_id) == f"/turni/scontro/{slot_id}"


def test_fixture_id_none_returns_fallback_without_querying() -> None:
    session = MagicMock()
    link = resolve_matchup_deep_link(session, team_id=uuid4(), fixture_id=None)
    assert link == "/turni"
    session.get.assert_not_called()
    session.scalar.assert_not_called()


def test_team_not_found_falls_back() -> None:
    session = MagicMock()
    session.get.return_value = None
    link = resolve_matchup_deep_link(session, team_id=uuid4(), fixture_id=uuid4())
    assert link == "/turni"


def test_happy_path_resolves_slot_id(monkeypatch: pytest.MonkeyPatch) -> None:
    team_id = uuid4()
    fixture_id = uuid4()
    league_id = uuid4()
    membership_id = uuid4()
    round_id = uuid4()
    calendar_id = uuid4()
    slot_id = uuid4()

    team = SimpleNamespace(league_id=league_id, membership_id=membership_id)
    round_fixture = SimpleNamespace(round_id=round_id)
    fantasy_round = SimpleNamespace(id=round_id, number=7)
    calendar = SimpleNamespace(id=calendar_id, league_id=league_id)
    slot = SimpleNamespace(id=slot_id)

    session = MagicMock()
    # session.get: prima FantasyTeam -> team, poi FantasyRound -> fantasy_round.
    session.get.side_effect = [team, fantasy_round]
    # session.scalar: FantasyRoundFixture, poi LeagueCalendar, poi LeagueCalendarSlot.
    session.scalar.side_effect = [round_fixture, calendar, slot]

    def _fake_h2h_round_numbers(*_args: object, **_kwargs: object) -> list[int]:
        return [7]

    monkeypatch.setattr(matchup_links, "h2h_round_numbers_for_round", _fake_h2h_round_numbers)

    link = resolve_matchup_deep_link(session, team_id=team_id, fixture_id=fixture_id)
    assert link == f"/turni/scontro/{slot_id}"


def test_no_round_fixture_mapping_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    team = SimpleNamespace(league_id=uuid4(), membership_id=uuid4())
    session = MagicMock()
    session.get.return_value = team
    session.scalar.return_value = None  # no FantasyRoundFixture for this league+fixture

    link = resolve_matchup_deep_link(session, team_id=uuid4(), fixture_id=uuid4())
    assert link == "/turni"


def test_no_calendar_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    team = SimpleNamespace(league_id=uuid4(), membership_id=uuid4())
    round_fixture = SimpleNamespace(round_id=uuid4())
    fantasy_round = SimpleNamespace(id=round_fixture.round_id, number=1)

    session = MagicMock()
    session.get.side_effect = [team, fantasy_round]
    session.scalar.side_effect = [round_fixture, None]  # no LeagueCalendar for the league

    link = resolve_matchup_deep_link(session, team_id=uuid4(), fixture_id=uuid4())
    assert link == "/turni"


def test_team_on_bye_that_round_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    team = SimpleNamespace(league_id=uuid4(), membership_id=uuid4())
    round_fixture = SimpleNamespace(round_id=uuid4())
    fantasy_round = SimpleNamespace(id=round_fixture.round_id, number=3)
    calendar = SimpleNamespace(id=uuid4(), league_id=team.league_id)

    session = MagicMock()
    session.get.side_effect = [team, fantasy_round]
    # No slot matches (the team was on a bye, or the data is inconsistent).
    session.scalar.side_effect = [round_fixture, calendar, None]
    monkeypatch.setattr(matchup_links, "h2h_round_numbers_for_round", lambda *args, **kwargs: [3])

    link = resolve_matchup_deep_link(session, team_id=uuid4(), fixture_id=uuid4())
    assert link == "/turni"


def test_custom_fallback_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    session = MagicMock()
    session.get.return_value = None
    link = resolve_matchup_deep_link(
        session, team_id=uuid4(), fixture_id=uuid4(), fallback="/formazione"
    )
    assert link == "/formazione"


def test_exception_is_swallowed_and_falls_back() -> None:
    session = MagicMock()
    session.get.side_effect = RuntimeError("boom")
    link = resolve_matchup_deep_link(session, team_id=uuid4(), fixture_id=uuid4())
    assert link == "/turni"
