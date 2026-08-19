"""Unit tests for listone provider refresh orchestration."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.enums import LeagueMemberRole, LeagueState
from leagues.listone_service import LeagueListoneService
from sports_data.listone.generate import ListoneGenerateCounters, ListoneGenerateResult
from sports_data.provider.errors import ProviderConfigError, ProviderRateLimitError
from sports_data.roster.sync import RosterSyncCounters, RosterSyncResult


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        return None


def _access(*, season_year: int = 2026) -> LeagueAccess:
    league = SimpleNamespace(id=uuid4(), season_year=season_year, state=LeagueState.AUCTION)
    user = SimpleNamespace(id=uuid4())
    return LeagueAccess(
        user=user,  # type: ignore[arg-type]
        league=league,  # type: ignore[arg-type]
        membership_role=LeagueMemberRole.OWNER,
    )


def test_refresh_maps_missing_provider_key(monkeypatch: pytest.MonkeyPatch) -> None:
    service = LeagueListoneService(_FakeSession())  # type: ignore[arg-type]
    monkeypatch.setattr(
        "leagues.listone_service.build_client_from_settings",
        lambda _settings: (_ for _ in ()).throw(ProviderConfigError("missing")),
    )
    monkeypatch.setattr("leagues.listone_service.get_api_settings", lambda: SimpleNamespace())

    with pytest.raises(ValidationAuthError) as exc:
        service.refresh_from_provider(_access())
    assert exc.value.code == "provider_key_missing"


def test_refresh_always_syncs_catalog_then_roster_listone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _FakeSession()
    service = LeagueListoneService(session)  # type: ignore[arg-type]
    calls: list[str] = []
    client = SimpleNamespace(closed=False)
    client.close = lambda: setattr(client, "closed", True)
    progress: list[tuple[int, str]] = []

    monkeypatch.setattr(
        LeagueListoneService,
        "_count_clubs_for_season",
        lambda self, year: 12,
    )
    monkeypatch.setattr(
        "leagues.listone_service.sync_mvp_catalog_with_client",
        lambda *_a, **_k: calls.append("catalog"),
    )

    def fake_roster(*_a, **kwargs):
        calls.append("roster")
        on_progress = kwargs.get("on_progress")
        if on_progress is not None:
            on_progress(1, 2, "Club A")
            on_progress(2, 2, "Club B")
        return RosterSyncResult(
            counters=RosterSyncCounters(
                athletes_created=1,
                memberships_created=1,
            )
        )

    monkeypatch.setattr("leagues.listone_service.sync_mvp_roster_with_client", fake_roster)
    monkeypatch.setattr(
        "leagues.listone_service.generate_official_listone",
        lambda *_a, **_k: calls.append("listone")
        or ListoneGenerateResult(
            season_year=2026,
            mapping_version="v1.0.0",
            counters=ListoneGenerateCounters(created=1, unchanged=0),
        ),
    )

    result = service.refresh_from_provider(
        _access(),
        client=client,  # type: ignore[arg-type]
        on_progress=lambda percent, stage, message: progress.append((percent, stage)),
    )
    assert calls == ["catalog", "roster", "listone"]
    assert result.counters.catalog_synced is True
    assert result.counters.listone_created == 1
    assert result.message.startswith("Listone aggiornato")
    assert len(session.added) == 1
    assert any(stage == "roster" for _, stage in progress)
    assert progress[-1] == (100, "completed")


def test_refresh_maps_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    service = LeagueListoneService(_FakeSession())  # type: ignore[arg-type]
    client = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(LeagueListoneService, "_count_clubs_for_season", lambda self, year: 3)
    monkeypatch.setattr(
        "leagues.listone_service.sync_mvp_catalog_with_client",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "leagues.listone_service.sync_mvp_roster_with_client",
        lambda *_a, **_k: (_ for _ in ()).throw(ProviderRateLimitError("429")),
    )
    with pytest.raises(ValidationAuthError) as exc:
        service.refresh_from_provider(_access(), client=client)  # type: ignore[arg-type]
    assert exc.value.code == "provider_rate_limited"
