"""Persist progress and lookup cache for the listone roster write."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from sports_data.roster.sync import (
    RosterSyncCounters,
    _latest_transfer_dates,
    _roster_cache,
    _RosterLookupCache,
    sync_roster,
    upsert_transfer,
)


class _QueryBoom:
    def execute(self, *_args, **_kwargs):
        raise AssertionError("lookup should use the roster cache")

    def scalars(self, *_args, **_kwargs):
        raise AssertionError("lookup should use the roster cache")


def test_sync_roster_reports_each_persist_step(monkeypatch) -> None:
    monkeypatch.setattr(
        "sports_data.roster.sync._load_roster_lookup_cache",
        lambda _session: _RosterLookupCache(),
    )
    monkeypatch.setattr("sports_data.roster.sync.sync_players_for_club", lambda *_a, **_k: None)
    monkeypatch.setattr("sports_data.roster.sync.sync_transfers", lambda *_a, **_k: None)
    monkeypatch.setattr("sports_data.roster.sync.sync_squads_for_club", lambda *_a, **_k: None)
    events: list[tuple[int, int, str]] = []

    sync_roster(
        SimpleNamespace(),  # type: ignore[arg-type]
        players_batches=[
            SimpleNamespace(
                envelope=None,
                club_provider_id=1,
                season_year=2026,
                label="Le Mans",
            ),
        ],
        transfers_envelopes=[SimpleNamespace()],
        squad_batches=[
            SimpleNamespace(
                envelope=None,
                club_provider_id=1,
                competition_provider_id=39,
                season_year=2026,
                label="Le Mans",
            ),
        ],
        on_progress=lambda done, total, label: events.append((done, total, label)),
    )

    assert events[0] == (0, 3, "Salvataggio rose…")
    assert events[1][2] == "Salvataggio rosa 1/1: Le Mans"
    assert events[2][2] == "Salvataggio trasferimenti 1/1"
    assert events[3] == (3, 3, "Salvataggio formazioni 1/1: Le Mans")
    assert _roster_cache.get() is None


def test_cached_transfer_key_skips_the_database() -> None:
    cache = _RosterLookupCache()
    cache.transfer_keys.add("already-stored")
    token = _roster_cache.set(cache)
    counters = RosterSyncCounters()
    try:
        result = upsert_transfer(
            _QueryBoom(),  # type: ignore[arg-type]
            SimpleNamespace(provider_key="already-stored"),  # type: ignore[arg-type]
            counters,
        )
    finally:
        _roster_cache.reset(token)

    assert result is None
    assert counters.transfers_unchanged == 1


def test_transfer_dates_cache_answers_without_a_query() -> None:
    athlete_id = uuid4()
    club_id = uuid4()
    cache = _RosterLookupCache()
    cache.transfer_outs[(athlete_id, club_id)] = date(2025, 9, 1)
    cache.transfer_ins[(athlete_id, club_id)] = date(2026, 7, 1)
    token = _roster_cache.set(cache)
    try:
        assert _latest_transfer_dates(
            _QueryBoom(),  # type: ignore[arg-type]
            athlete_id=athlete_id,
            club_id=club_id,
        ) == (date(2025, 9, 1), date(2026, 7, 1))
        assert _latest_transfer_dates(
            _QueryBoom(),  # type: ignore[arg-type]
            athlete_id=uuid4(),
            club_id=club_id,
        ) == (None, None)
    finally:
        _roster_cache.reset(token)
