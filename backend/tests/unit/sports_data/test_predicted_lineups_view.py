"""Vista delle formazioni probabili per il dettaglio partita (TASK 2).

Sessione finta (``MagicMock``), stesso approccio di ``test_probable_hints.py``
e ``test_predicted_lineups_diagnosis.py``: niente DB reale.

Prima di questa correzione, ``PredictedViewPlayer`` esponeva già i
panchinari (erano parsati e salvati, solo non arricchiti), ma senza
``ruolo`` né ``ordine panchina``: la UI non aveva modo di distinguerli dai
titolari né di ordinarli per probabilità di impiego.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from sports_data.predicted.models import PredictedLineupPlayer, PredictedLineupSnapshot
from sports_data.predicted.read import latest_predicted_view


def _session_with(*, snapshot: PredictedLineupSnapshot | None, role_rows: list[tuple]) -> MagicMock:
    session = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = snapshot
    session.scalars.return_value = scalars_mock
    session.execute.return_value.all.return_value = role_rows
    return session


def test_bench_players_are_exposed_with_role_and_bench_order() -> None:
    starter_id = uuid4()
    first_sub_id = uuid4()
    second_sub_id = uuid4()
    fixture_id = uuid4()

    players = [
        PredictedLineupPlayer(
            athlete_id=starter_id,
            side="home",
            display_name="Starter One",
            is_starter=True,
            is_unavailable=False,
            sort_order=1,
        ),
        PredictedLineupPlayer(
            athlete_id=first_sub_id,
            side="home",
            display_name="Bench One",
            is_starter=False,
            is_unavailable=False,
            sort_order=12,
        ),
        # Non abbinato alla rosa: resta in panchina comunque, senza ruolo.
        PredictedLineupPlayer(
            athlete_id=second_sub_id,
            side="home",
            display_name="Bench Two",
            is_starter=False,
            is_unavailable=False,
            sort_order=13,
        ),
    ]
    snapshot = PredictedLineupSnapshot(
        fixture_id=fixture_id,
        fotmob_match_id=None,
        lineup_type="predicted",
        source="fotmob",
        reliability="validated",
        warning_codes=[],
        fetched_at=datetime(2026, 10, 20, tzinfo=UTC),
        home_formation="4-3-3",
        players=players,
    )
    session = _session_with(
        snapshot=snapshot,
        role_rows=[
            (starter_id, "Midfielder"),
            (first_sub_id, "Defender"),
            # second_sub_id non ha una riga di rosa: resta senza ruolo noto.
        ],
    )

    view = latest_predicted_view(session, fixture_id)
    assert view is not None
    assert view.home is not None

    [starter] = view.home.starters
    assert starter.role == "C"
    assert starter.bench_order is None

    bench_by_name = {row.name: row for row in view.home.bench}
    assert len(bench_by_name) == 2
    assert bench_by_name["Bench One"].role == "D"
    assert bench_by_name["Bench One"].bench_order == 1
    assert bench_by_name["Bench Two"].role is None
    assert bench_by_name["Bench Two"].bench_order == 2
    # L'ordine di panchina è relativo alla panchina, non al sort_order grezzo
    # (che qui conta anche il titolare a sort_order 1).
    assert {row.bench_order for row in view.home.bench} == {1, 2}


def test_unmapped_bench_player_still_gets_a_bench_order() -> None:
    fixture_id = uuid4()
    unmapped = PredictedLineupPlayer(
        athlete_id=None,
        side="away",
        display_name="M. Rossi",
        is_starter=False,
        is_unavailable=False,
        sort_order=1,
    )
    snapshot = PredictedLineupSnapshot(
        fixture_id=fixture_id,
        fotmob_match_id=None,
        lineup_type="predicted",
        source="fotmob",
        reliability="unverified",
        warning_codes=[],
        fetched_at=datetime(2026, 10, 20, tzinfo=UTC),
        away_formation="4-4-2",
        players=[unmapped],
    )
    session = _session_with(snapshot=snapshot, role_rows=[])

    view = latest_predicted_view(session, fixture_id)
    assert view is not None
    assert view.away is not None
    [bench_player] = view.away.bench
    assert bench_player.athlete_id is None
    assert bench_player.role is None
    assert bench_player.bench_order == 1


def test_no_snapshot_returns_none() -> None:
    session = _session_with(snapshot=None, role_rows=[])
    assert latest_predicted_view(session, uuid4()) is None
