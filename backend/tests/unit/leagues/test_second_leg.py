"""Girone di ritorno: motore puro (TASK 9)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from leagues.second_leg import (
    evaluate_second_leg,
    fixture_has_started,
    parse_round_number,
)


def test_parse_round_number_extracts_trailing_integer() -> None:
    assert parse_round_number("Regular Season - 15") == 15
    assert parse_round_number("Regular Season - 1") == 1


def test_parse_round_number_none_for_missing_or_non_numeric_label() -> None:
    assert parse_round_number(None) is None
    assert parse_round_number("") is None
    assert parse_round_number("Quarter-finals") is None


def test_fixture_has_started_true_for_live_or_finished_status() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert fixture_has_started(status_short="FT", kickoff_at=None, now=now)
    assert fixture_has_started(status_short="1H", kickoff_at=None, now=now)


def test_fixture_has_started_false_for_postponed_even_if_kickoff_passed() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    kickoff = now - timedelta(days=1)
    assert not fixture_has_started(status_short="PST", kickoff_at=kickoff, now=now)


def test_fixture_has_started_uses_kickoff_when_status_not_yet_updated() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    past_kickoff = now - timedelta(hours=2)
    future_kickoff = now + timedelta(hours=2)
    assert fixture_has_started(status_short="NS", kickoff_at=past_kickoff, now=now)
    assert not fixture_has_started(status_short="NS", kickoff_at=future_kickoff, now=now)


def test_fixture_has_started_false_without_kickoff_or_status() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert not fixture_has_started(status_short=None, kickoff_at=None, now=now)


def test_evaluate_second_leg_no_schedule_data_when_no_rounds_seen() -> None:
    status = evaluate_second_leg([], [])
    assert status.has_schedule_data is False
    assert status.second_leg_started is False
    assert status.total_rounds is None


def test_evaluate_second_leg_not_started_before_halfway() -> None:
    # 38 giornate (20 squadre): girone di ritorno inizia alla 20.
    rounds = set(range(1, 39))
    started = set(range(1, 12))  # fino alla giornata 11 inclusa
    status = evaluate_second_leg(rounds, started)
    assert status.has_schedule_data is True
    assert status.total_rounds == 38
    assert status.current_round == 11
    assert status.second_leg_start_round == 20
    assert status.second_leg_started is False


def test_evaluate_second_leg_started_at_exact_boundary_round() -> None:
    rounds = set(range(1, 39))
    started = set(range(1, 21))  # giornata 20 già iniziata = prima di ritorno
    status = evaluate_second_leg(rounds, started)
    assert status.second_leg_start_round == 20
    assert status.current_round == 20
    assert status.second_leg_started is True


def test_evaluate_second_leg_not_started_one_round_before_boundary() -> None:
    rounds = set(range(1, 39))
    started = set(range(1, 20))  # fermo alla giornata 19, ultima di andata
    status = evaluate_second_leg(rounds, started)
    assert status.current_round == 19
    assert status.second_leg_started is False


def test_evaluate_second_leg_single_round_competition_never_blocks() -> None:
    status = evaluate_second_leg({1}, {1})
    assert status.has_schedule_data is True
    assert status.total_rounds == 1
    assert status.second_leg_start_round is None
    assert status.second_leg_started is False


def test_evaluate_second_leg_ignores_started_rounds_outside_known_rounds() -> None:
    # Una giornata "iniziata" che non fa parte dell'insieme visto (dato
    # incoerente) non deve alterare il calcolo del current_round.
    status = evaluate_second_leg({1, 2, 3, 4}, {99})
    assert status.current_round == 0
    assert status.second_leg_started is False
