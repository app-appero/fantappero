"""Sport Data (SPD) anti-corruption layer — provider I/O and normalization."""

from sports_data.catalog import (
    Club,
    CompetitionSeasonClub,
    SportSeason,
    TeamsBatch,
    sync_catalog,
    sync_mvp_catalog_with_client,
)
from sports_data.normalization import (
    AnomalyCode,
    EventStatus,
    NormalizationResult,
    NormalizedScoringEvent,
    ScoringEventKind,
    normalize_scoring_events,
)
from sports_data.provider import (
    PROVIDER_NAME,
    ApiFootballClient,
    ProviderEnvelope,
    ProviderSnapshot,
    build_client_from_settings,
    map_clubs,
    map_competitions,
    map_fixtures,
    map_seasons,
    store_provider_snapshot,
)

__all__ = [
    "AnomalyCode",
    "ApiFootballClient",
    "Club",
    "CompetitionSeasonClub",
    "EventStatus",
    "NormalizationResult",
    "NormalizedScoringEvent",
    "PROVIDER_NAME",
    "ProviderEnvelope",
    "ProviderSnapshot",
    "ScoringEventKind",
    "SportSeason",
    "TeamsBatch",
    "build_client_from_settings",
    "map_clubs",
    "map_competitions",
    "map_fixtures",
    "map_seasons",
    "normalize_scoring_events",
    "store_provider_snapshot",
    "sync_catalog",
    "sync_mvp_catalog_with_client",
]
