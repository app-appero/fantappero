"""Unit tests for the platform-wide listone provider refresh orchestration (EP11-04b)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from admin.listone_service import refresh_platform_listone
from auth.exceptions import ValidationAuthError
from sports_data.listone.generate import ListoneGenerateCounters, ListoneGenerateResult
from sports_data.provider.errors import ProviderConfigError, ProviderRateLimitError
from sports_data.roster.sync import RosterSyncCounters, RosterSyncResult


class _FakeSession:
    def flush(self) -> None:
        return None


def test_platform_refresh_maps_missing_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "admin.listone_service.build_client_from_settings",
        lambda _settings: (_ for _ in ()).throw(ProviderConfigError("missing")),
    )
    monkeypatch.setattr("admin.listone_service.get_api_settings", lambda: SimpleNamespace())

    with pytest.raises(ValidationAuthError) as exc:
        refresh_platform_listone(_FakeSession(), season_year=2026)  # type: ignore[arg-type]
    assert exc.value.code == "provider_key_missing"
    assert "API_FOOTBALL" not in exc.value.message
    assert "backend" not in exc.value.message.lower()


def test_platform_refresh_syncs_catalog_then_roster_listone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    client = SimpleNamespace(closed=False)
    client.close = lambda: setattr(client, "closed", True)
    progress: list[tuple[int, str]] = []

    monkeypatch.setattr(
        "admin.listone_service._count_clubs_for_season",
        lambda _session, _year: 12,
    )
    monkeypatch.setattr(
        "admin.listone_service.sync_mvp_catalog_with_client",
        lambda *_a, **_k: calls.append("catalog"),
    )

    def fake_roster(*_a, **kwargs):
        calls.append("roster")
        on_progress = kwargs.get("on_progress")
        if on_progress is not None:
            on_progress(1, 2, "Club A")
            on_progress(2, 2, "Club B")
        return RosterSyncResult(
            counters=RosterSyncCounters(athletes_created=1, memberships_created=1)
        )

    monkeypatch.setattr("admin.listone_service.sync_mvp_roster_with_client", fake_roster)
    monkeypatch.setattr(
        "admin.listone_service.generate_official_listone",
        lambda *_a, **_k: calls.append("listone")
        or ListoneGenerateResult(
            season_year=2026,
            mapping_version="v1.0.0",
            counters=ListoneGenerateCounters(created=1, unchanged=0),
        ),
    )

    result = refresh_platform_listone(
        _FakeSession(),  # type: ignore[arg-type]
        season_year=2026,
        client=client,  # type: ignore[arg-type]
        on_progress=lambda percent, stage, message: progress.append((percent, stage)),
    )
    assert calls == ["catalog", "roster", "listone"]
    assert result.counters.catalog_synced is True
    assert result.counters.listone_created == 1
    assert result.message.startswith("Listone aggiornato")
    assert any(stage == "roster" for _, stage in progress)
    assert progress[-1] == (100, "completed")


def test_platform_refresh_keeps_moving_while_rosters_are_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The last fetched club used to freeze the bar at 90% for the whole write."""
    client = SimpleNamespace(close=lambda: None)
    progress: list[tuple[int, str, str]] = []
    monkeypatch.setattr("admin.listone_service._count_clubs_for_season", lambda _s, _y: 12)
    monkeypatch.setattr(
        "admin.listone_service.sync_mvp_catalog_with_client",
        lambda *_a, **_k: None,
    )

    def fake_roster(*_a, **kwargs):
        on_progress = kwargs["on_progress"]
        on_progress(96, 96, "Le Mans")
        on_progress(0, 2, "Salvataggio rose…")
        on_progress(1, 2, "Salvataggio rosa 1/2: Le Mans")
        on_progress(2, 2, "Salvataggio rosa 2/2: Le Mans")
        return RosterSyncResult(counters=RosterSyncCounters())

    monkeypatch.setattr("admin.listone_service.sync_mvp_roster_with_client", fake_roster)
    monkeypatch.setattr(
        "admin.listone_service.generate_official_listone",
        lambda *_a, **kwargs: (
            kwargs["on_progress"](1, 2),
            kwargs["on_progress"](2, 2),
            ListoneGenerateResult(
                season_year=2026,
                mapping_version="v1.0.0",
                counters=ListoneGenerateCounters(created=1),
            ),
        )[-1],
    )

    refresh_platform_listone(
        _FakeSession(),  # type: ignore[arg-type]
        season_year=2026,
        client=client,  # type: ignore[arg-type]
        on_progress=lambda percent, stage, message: progress.append((percent, stage, message)),
    )

    roster = [(percent, message) for percent, stage, message in progress if stage == "roster"]
    assert roster[0] == (55, "Rosa 96/96: Le Mans")
    assert roster[1][1] == "Salvataggio rose…"
    assert roster[-1] == (90, "Salvataggio rosa 2/2: Le Mans")
    percents = [percent for percent, _message in roster]
    assert percents == sorted(percents)
    listone = [percent for percent, stage, _message in progress if stage == "listone"]
    assert listone[0] == 92
    assert listone[-1] == 99
    assert progress[-1][0] == 100


def test_platform_refresh_maps_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    client = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr("admin.listone_service._count_clubs_for_season", lambda _s, _y: 3)
    monkeypatch.setattr(
        "admin.listone_service.sync_mvp_catalog_with_client",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "admin.listone_service.sync_mvp_roster_with_client",
        lambda *_a, **_k: (_ for _ in ()).throw(ProviderRateLimitError("429")),
    )
    with pytest.raises(ValidationAuthError) as exc:
        refresh_platform_listone(
            _FakeSession(), season_year=2026, client=client  # type: ignore[arg-type]
        )
    assert exc.value.code == "provider_rate_limited"
