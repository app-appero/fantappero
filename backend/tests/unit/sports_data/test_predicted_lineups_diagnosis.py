"""Perché un giocatore non ha un indizio di formazione probabile (pannello operatore).

Sessione finta (``MagicMock``), stesso approccio di ``test_probable_hints.py``:
niente DB reale, solo il controllo del percorso che sceglie ``diagnose_hints``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from sports_data.predicted.models import PredictedLineupPlayer, PredictedLineupSnapshot
from sports_data.predicted.read import diagnose_hints
from sports_data.roster.models import Athlete


def _session_with(*, scalars_results: list[list[object]], execute_result: list[tuple]) -> MagicMock:
    session = MagicMock()
    scalar_mocks = []
    for rows in scalars_results:
        mock = MagicMock()
        mock.all.return_value = rows
        scalar_mocks.append(mock)
    session.scalars.side_effect = scalar_mocks
    session.execute.return_value.all.return_value = execute_result
    return session


def _athlete(**overrides: object) -> Athlete:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "provider_id": 1,
        "canonical_name": "Mario Rossi",
        "first_name": "Mario",
        "last_name": "Rossi",
    }
    defaults.update(overrides)
    return Athlete(**defaults)


def test_empty_athlete_list_short_circuits() -> None:
    session = MagicMock()
    assert diagnose_hints(session, uuid4(), []) == ()
    session.scalars.assert_not_called()
    session.execute.assert_not_called()


def test_no_active_squad_when_athlete_has_no_club() -> None:
    athlete_id = uuid4()
    athlete = _athlete(id=athlete_id)
    session = _session_with(
        scalars_results=[[athlete], []],  # Athlete, poi SquadMembership vuoto
        execute_result=[],  # nessuna fixture nel turno (non conta: manca il club)
    )

    result = diagnose_hints(session, uuid4(), [athlete_id])
    assert len(result) == 1
    assert result[0].reason == "no_active_squad"
    assert result[0].hint is None


def test_no_fixture_in_round_when_club_not_in_window() -> None:
    athlete_id = uuid4()
    club_id = uuid4()
    other_home, other_away = uuid4(), uuid4()
    fixture_x = uuid4()
    athlete = _athlete(id=athlete_id)
    membership = MagicMock(athlete_id=athlete_id, club_id=club_id)
    club_row = MagicMock(id=club_id)
    club_row.name = "Il Club"  # "name" è riservato dal costruttore di MagicMock
    session = _session_with(
        scalars_results=[
            [athlete],  # Athlete
            [membership],  # SquadMembership
            [club_row],  # Club (serve solo per il nome, club_id incluso nei club_ids)
            [],  # PredictedLineupSnapshot (fixture_ids non vuoto ma nessuno snapshot)
        ],
        execute_result=[(fixture_x, other_home, other_away)],  # il club dell'atleta non c'è
    )

    result = diagnose_hints(session, uuid4(), [athlete_id])
    assert result[0].reason == "no_fixture_in_round"
    assert result[0].club_name == "Il Club"


def test_no_snapshot_yet_when_fixture_linked_but_nothing_downloaded() -> None:
    athlete_id = uuid4()
    club_id = uuid4()
    fixture_id = uuid4()
    athlete = _athlete(id=athlete_id)
    membership = MagicMock(athlete_id=athlete_id, club_id=club_id)
    session = _session_with(
        scalars_results=[[athlete], [membership], [], []],
        execute_result=[(fixture_id, club_id, uuid4())],
    )

    result = diagnose_hints(session, uuid4(), [athlete_id])
    assert result[0].reason == "no_snapshot_yet"
    assert result[0].fixture_id == fixture_id


def test_snapshot_not_usable_when_reliability_below_threshold() -> None:
    athlete_id = uuid4()
    club_id = uuid4()
    fixture_id = uuid4()
    athlete = _athlete(id=athlete_id)
    membership = MagicMock(athlete_id=athlete_id, club_id=club_id)
    snapshot = PredictedLineupSnapshot(
        fixture_id=fixture_id,
        fotmob_match_id=None,
        lineup_type="predicted",
        source="soccer_oracle:predicted",
        reliability="unverified",
        warning_codes=[],
        fetched_at=datetime(2026, 10, 20, tzinfo=UTC),
        players=[],
    )
    session = _session_with(
        scalars_results=[[athlete], [membership], [], [snapshot]],
        execute_result=[(fixture_id, club_id, uuid4())],
    )

    result = diagnose_hints(session, uuid4(), [athlete_id])
    assert result[0].reason == "snapshot_not_usable"
    assert "unverified" in result[0].detail


def test_unmapped_surfaces_a_similar_unmatched_name() -> None:
    athlete_id = uuid4()
    club_id = uuid4()
    fixture_id = uuid4()
    athlete = _athlete(id=athlete_id, canonical_name="Mario Rossi", last_name="Rossi")
    membership = MagicMock(athlete_id=athlete_id, club_id=club_id)
    unmatched_player = PredictedLineupPlayer(
        athlete_id=None,
        side="home",
        display_name="M. Rossi",
        is_starter=True,
        is_unavailable=False,
    )
    snapshot = PredictedLineupSnapshot(
        fixture_id=fixture_id,
        fotmob_match_id=None,
        lineup_type="predicted",
        source="soccer_oracle:predicted",
        reliability="partially_validated",
        warning_codes=[],
        fetched_at=datetime(2026, 10, 20, tzinfo=UTC),
        players=[unmatched_player],
    )
    session = _session_with(
        scalars_results=[[athlete], [membership], [], [snapshot]],
        execute_result=[(fixture_id, club_id, uuid4())],
    )

    result = diagnose_hints(session, uuid4(), [athlete_id])
    assert result[0].reason == "unmapped_in_snapshot"
    assert result[0].similar_unmatched_names == ("M. Rossi",)


def test_hinted_when_the_player_row_resolves_to_the_athlete() -> None:
    athlete_id = uuid4()
    club_id = uuid4()
    fixture_id = uuid4()
    athlete = _athlete(id=athlete_id)
    membership = MagicMock(athlete_id=athlete_id, club_id=club_id)
    mapped_player = PredictedLineupPlayer(
        athlete_id=athlete_id,
        side="home",
        display_name="Mario Rossi",
        is_starter=True,
        is_unavailable=False,
    )
    snapshot = PredictedLineupSnapshot(
        fixture_id=fixture_id,
        fotmob_match_id=None,
        lineup_type="predicted",
        source="soccer_oracle:predicted",
        reliability="validated",
        warning_codes=[],
        fetched_at=datetime(2026, 10, 20, tzinfo=UTC),
        players=[mapped_player],
    )
    session = _session_with(
        scalars_results=[[athlete], [membership], [], [snapshot]],
        execute_result=[(fixture_id, club_id, uuid4())],
    )

    result = diagnose_hints(session, uuid4(), [athlete_id])
    assert result[0].reason == "hinted"
    assert result[0].hint == "starter"
