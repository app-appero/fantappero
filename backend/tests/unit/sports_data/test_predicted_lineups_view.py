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

from sports_data.fixtures.models import Fixture
from sports_data.predicted.models import PredictedLineupPlayer, PredictedLineupSnapshot
from sports_data.predicted.read import hints_for_fixtures, latest_predicted_view


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


def test_bench_inferred_from_squad_when_fotmob_omits_it() -> None:
    """FotMob a volte non pubblica affatto la panchina (solo titolari e
    indisponibili): chi è in rosa reale e non rientra in nessuno dei due
    gruppi viene dedotto come possibile panchina, finché la formazione
    resta "predicted" e la partita non è iniziata (EP-panchina-dedotta)."""
    fixture_id = uuid4()
    club_id = uuid4()
    season_id = uuid4()
    starter_id = uuid4()
    unavailable_id = uuid4()
    bench_one = uuid4()
    bench_two = uuid4()

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
            athlete_id=unavailable_id,
            side="home",
            display_name="Injured One",
            is_starter=False,
            is_unavailable=True,
            unavailability_type="injury",
            unavailability_label="Infortunato",
            blocks_selection=True,
            sort_order=2,
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
    fixture = Fixture(
        id=fixture_id,
        provider_id=1,
        sport_season_id=season_id,
        home_club_id=club_id,
        away_club_id=uuid4(),
        status_short="NS",
    )

    session = MagicMock()
    session.get.return_value = fixture
    snapshot_scalars = MagicMock()
    snapshot_scalars.first.return_value = snapshot
    squad_scalars = MagicMock()
    squad_scalars.all.return_value = [starter_id, unavailable_id, bench_one, bench_two]
    session.scalars.side_effect = [snapshot_scalars, squad_scalars]

    roles_execute = MagicMock()
    roles_execute.all.return_value = []
    inferred_roles_execute = MagicMock()
    inferred_roles_execute.all.return_value = [(bench_one, "Defender")]
    names_execute = MagicMock()
    names_execute.all.return_value = [(bench_one, "Bench One"), (bench_two, "Bench Two")]
    session.execute.side_effect = [roles_execute, inferred_roles_execute, names_execute]

    view = latest_predicted_view(session, fixture_id)
    assert view is not None
    assert view.home is not None
    bench_by_name = {row.name: row for row in view.home.bench}
    assert set(bench_by_name) == {"Bench One", "Bench Two"}
    assert {row.athlete_id for row in view.home.bench} == {str(bench_one), str(bench_two)}
    assert bench_by_name["Bench One"].role == "D"
    assert bench_by_name["Bench Two"].role is None
    assert {row.bench_order for row in view.home.bench} == {1, 2}


def test_bench_not_inferred_once_the_match_has_started() -> None:
    """Una volta partita la gara, FotMob pubblica sempre la panchina vera:
    l'inferenza non deve più scattare, anche se lo snapshot resta "predicted"."""
    fixture_id = uuid4()
    club_id = uuid4()
    starter_id = uuid4()

    players = [
        PredictedLineupPlayer(
            athlete_id=starter_id,
            side="home",
            display_name="Starter One",
            is_starter=True,
            is_unavailable=False,
            sort_order=1,
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
    fixture = Fixture(
        id=fixture_id,
        provider_id=1,
        sport_season_id=uuid4(),
        home_club_id=club_id,
        away_club_id=uuid4(),
        status_short="1H",
    )

    session = MagicMock()
    session.get.return_value = fixture
    snapshot_scalars = MagicMock()
    snapshot_scalars.first.return_value = snapshot
    session.scalars.return_value = snapshot_scalars
    session.execute.return_value.all.return_value = []

    view = latest_predicted_view(session, fixture_id)
    assert view is not None
    assert view.home is not None
    assert view.home.bench == ()
    # Nessuna query sulla rosa reale: l'inferenza non deve nemmeno tentare.
    assert session.scalars.call_count == 1


def test_hints_for_fixtures_infers_bench_when_fotmob_omits_it() -> None:
    """Stessa inferenza di ``latest_predicted_view``, ma per l'illuminazione
    (Formazione e Turni Fantallenatori): chi è in rosa e non è né titolare
    né indisponibile prende hint "bench", con nota distinta da chi è
    bench perché FotMob lo dice davvero."""
    fixture_id = uuid4()
    club_id = uuid4()
    away_club_id = uuid4()
    season_id = uuid4()
    starter_id = uuid4()
    bench_one = uuid4()
    away_starter_id = uuid4()
    away_bench_id = uuid4()

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
            athlete_id=away_starter_id,
            side="away",
            display_name="Away Starter",
            is_starter=True,
            is_unavailable=False,
            sort_order=1,
        ),
        PredictedLineupPlayer(
            athlete_id=away_bench_id,
            side="away",
            display_name="Away Bench",
            is_starter=False,
            is_unavailable=False,
            sort_order=12,
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
        away_formation="4-4-2",
        players=players,
    )
    fixture = Fixture(
        id=fixture_id,
        provider_id=1,
        sport_season_id=season_id,
        home_club_id=club_id,
        away_club_id=away_club_id,
        status_short="NS",
    )

    session = MagicMock()
    snapshots_scalars = MagicMock()
    snapshots_scalars.all.return_value = [snapshot]
    fixtures_scalars = MagicMock()
    fixtures_scalars.all.return_value = [fixture]
    squad_scalars = MagicMock()
    squad_scalars.all.return_value = [starter_id, bench_one]
    session.scalars.side_effect = [snapshots_scalars, fixtures_scalars, squad_scalars]

    hints = hints_for_fixtures(session, [fixture_id], [starter_id, bench_one, away_bench_id])

    assert hints[starter_id].hint == "starter"
    assert hints[away_bench_id].hint == "bench"
    assert hints[away_bench_id].note == "Possibile panchina"
    assert hints[bench_one].hint == "bench"
    assert hints[bench_one].note == "Possibile panchina (dedotta)"


def test_no_snapshot_returns_none() -> None:
    session = _session_with(snapshot=None, role_rows=[])
    assert latest_predicted_view(session, uuid4()) is None
