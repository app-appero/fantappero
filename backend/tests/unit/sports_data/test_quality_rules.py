"""Unit tests for sports data quality detection rules (EP04-07)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from sports_data.quality.rules import (
    FixtureQualitySnapshot,
    build_fingerprint,
    detect_all,
    detect_conflicts,
    detect_corrections,
    detect_delays,
    detect_missing,
    validate_retry_target,
)
from sports_data.quality.types import QualityIssueCode, QualityIssueKind


def _snap(**kwargs) -> FixtureQualitySnapshot:
    base = dict(
        fixture_id=uuid4(),
        fixture_provider_id=1035055,
        status_short="FT",
        kickoff_at=datetime(2024, 1, 1, 15, 0, tzinfo=UTC),
        active_event_count=5,
        lineup_count=2,
        stats_count=20,
    )
    base.update(kwargs)
    return FixtureQualitySnapshot(**base)


def test_fingerprint_stable_for_idempotency() -> None:
    a = build_fingerprint(code=QualityIssueCode.MISSING_EVENTS, fixture_provider_id=1035055)
    b = build_fingerprint(code=QualityIssueCode.MISSING_EVENTS, fixture_provider_id=1035055)
    assert a == b
    assert a == "missing_events:1035055:fixture"


def test_detect_missing_on_finished_fixture() -> None:
    findings = detect_missing(
        _snap(active_event_count=0, lineup_count=0, stats_count=0),
    )
    codes = {f.code for f in findings}
    assert codes == {
        QualityIssueCode.MISSING_EVENTS,
        QualityIssueCode.MISSING_LINEUPS,
        QualityIssueCode.MISSING_STATS,
    }
    assert all(f.kind == QualityIssueKind.MISSING for f in findings)


def test_detect_missing_skips_non_finished() -> None:
    assert detect_missing(_snap(status_short="NS", active_event_count=0)) == []


def test_detect_postponed_and_overdue() -> None:
    now = datetime(2024, 1, 2, tzinfo=UTC)
    postponed = detect_delays(_snap(status_short="PST"), now=now)
    assert len(postponed) == 1
    assert postponed[0].code == QualityIssueCode.POSTPONED

    overdue = detect_delays(
        _snap(
            status_short="NS",
            kickoff_at=now - timedelta(hours=2),
            active_event_count=0,
            lineup_count=0,
            stats_count=0,
        ),
        now=now,
    )
    assert any(f.code == QualityIssueCode.KICKOFF_OVERDUE for f in overdue)


def test_detect_conflicts_and_corrections() -> None:
    snap = _snap(
        conflict_events=(("events|1|primary", ("goal_count_mismatch",), "anomaly"),),
        retracted_events=(("events|2|primary", datetime(2024, 1, 1, tzinfo=UTC)),),
    )
    conflicts = detect_conflicts(snap)
    assert len(conflicts) == 1
    assert conflicts[0].kind == QualityIssueKind.CONFLICT
    assert "events|1|primary" in conflicts[0].fingerprint

    corrections = detect_corrections(snap)
    assert len(corrections) == 1
    assert corrections[0].code == QualityIssueCode.EVENT_RETRACTED


def test_detect_all_combines_rules() -> None:
    findings = detect_all(
        _snap(status_short="PST", active_event_count=0, lineup_count=0, stats_count=0),
        now=datetime(2024, 1, 2, tzinfo=UTC),
    )
    kinds = {f.kind for f in findings}
    assert QualityIssueKind.DELAY in kinds
    # PST is not finished → no missing
    assert QualityIssueKind.MISSING not in kinds


def test_validate_retry_target() -> None:
    validate_retry_target(fixture_provider_id=1035055)
    with pytest.raises(ValueError):
        validate_retry_target(fixture_provider_id=0)
    with pytest.raises(ValueError):
        validate_retry_target(fixture_provider_id=None)  # type: ignore[arg-type]
