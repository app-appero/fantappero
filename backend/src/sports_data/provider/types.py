"""Internal DTOs for API-Football envelope and mapped entities (EP04-01)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class ProviderPaging:
    current: int
    total: int


@dataclass(frozen=True)
class ProviderRateLimit:
    """Quota headers from API-Sports (names vary slightly by gateway)."""

    limit: int | None = None
    remaining: int | None = None


@dataclass(frozen=True)
class ProviderEnvelope:
    """Normalized view of one API-Football v3 response page."""

    endpoint: str
    parameters: dict[str, str]
    errors: Any
    results: int
    paging: ProviderPaging
    response: list[Any]
    rate_limit: ProviderRateLimit | None = None
    http_status: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def has_errors(self) -> bool:
        if self.errors is None:
            return False
        if isinstance(self.errors, list):
            return len(self.errors) > 0
        if isinstance(self.errors, dict):
            return len(self.errors) > 0
        if isinstance(self.errors, str):
            return bool(self.errors.strip())
        return bool(self.errors)


@dataclass(frozen=True)
class MappedCompetition:
    """ACL competition candidate (provider ids only — no fantasy UUID yet)."""

    provider_id: int
    name: str
    country: str
    season_year: int | None = None
    season_current: bool | None = None
    coverage_events: bool | None = None
    coverage_lineups: bool | None = None
    coverage_statistics_players: bool | None = None


@dataclass(frozen=True)
class MappedSeason:
    """Season row under a competition (``/leagues`` seasons[])."""

    competition_provider_id: int
    year: int
    is_current: bool
    start_date: date | None = None
    end_date: date | None = None
    coverage_events: bool | None = None
    coverage_lineups: bool | None = None
    coverage_statistics_players: bool | None = None
    coverage_injuries: bool | None = None
    coverage_predictions: bool | None = None
    coverage_standings: bool | None = None


@dataclass(frozen=True)
class MappedClub:
    provider_id: int
    name: str
    code: str | None = None
    country: str | None = None
    logo_url: str | None = None
    national: bool = False


@dataclass(frozen=True)
class MappedFixture:
    provider_id: int
    competition_provider_id: int
    season_year: int
    home_club_provider_id: int
    away_club_provider_id: int
    kickoff_at: datetime | None
    status_short: str
    home_goals: int | None = None
    away_goals: int | None = None
    status_elapsed: int | None = None
    round_label: str | None = None
    home_club_name: str | None = None
    away_club_name: str | None = None
    venue_name: str | None = None
    venue_city: str | None = None
    referee: str | None = None


@dataclass(frozen=True)
class MappedMatchEvent:
    """Raw timeline event from ``/fixtures/events`` (idempotent provider key)."""

    provider_event_key: str
    fixture_provider_id: int
    event_type: str
    event_detail: str | None
    athlete_provider_id: int | None
    related_athlete_provider_id: int | None
    club_provider_id: int | None
    minute_elapsed: int | None
    minute_extra: int | None
    comments: str | None = None


@dataclass(frozen=True)
class MappedLineupEntry:
    athlete_provider_id: int
    athlete_name: str
    is_starter: bool
    shirt_number: int | None = None
    position_raw: str | None = None
    grid: str | None = None
    sort_order: int = 0


@dataclass(frozen=True)
class MappedOfficialLineup:
    """Official lineup for one club in a fixture."""

    fixture_provider_id: int
    club_provider_id: int
    formation: str | None
    coach_name: str | None = None
    entries: tuple[MappedLineupEntry, ...] = ()


@dataclass(frozen=True)
class MappedPlayerMatchStat:
    """Per-player match statistics from ``/fixtures/players``."""

    fixture_provider_id: int
    athlete_provider_id: int
    athlete_name: str
    club_provider_id: int | None
    minutes: int | None
    position_raw: str | None
    is_substitute: bool | None
    provider_rating: str | None
    stats: dict[str, Any] = field(default_factory=dict)
    stats_hash: str = ""


@dataclass(frozen=True)
class MappedAthlete:
    """ACL athlete candidate from ``/players`` or ``/players/squads``."""

    provider_id: int
    canonical_name: str
    first_name: str | None = None
    last_name: str | None = None
    nationality: str | None = None
    birth_date: date | None = None
    height: str | None = None
    weight: str | None = None
    age: int | None = None
    injured: bool | None = None
    photo_url: str | None = None


@dataclass(frozen=True)
class MappedSquadMembership:
    """Squad row scoped to club + season context."""

    athlete_provider_id: int
    athlete_name: str
    club_provider_id: int
    competition_provider_id: int
    season_year: int
    shirt_number: int | None = None
    provider_position_raw: str | None = None
    athlete_age: int | None = None
    source: str = "squads"
    photo_url: str | None = None


@dataclass(frozen=True)
class MappedTransfer:
    """Single transfer entry under a ``/transfers`` player block."""

    athlete_provider_id: int
    athlete_name: str
    transfer_date: date
    from_club_provider_id: int | None
    to_club_provider_id: int | None
    transfer_type: str
    provider_key: str
