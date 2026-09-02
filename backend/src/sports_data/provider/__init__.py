"""API-Football v3 adapter — authentication, pagination, errors, mapping (EP04-01)."""

from sports_data.provider.client import ApiFootballClient, build_client_from_settings
from sports_data.provider.constants import MVP_LEAGUE_IDS, PROVIDER_NAME
from sports_data.provider.envelope import merge_envelopes, parse_envelope
from sports_data.provider.errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderHttpError,
    ProviderRateLimitError,
    ProviderResponseError,
)
from sports_data.provider.hashing import payload_sha256, request_fingerprint
from sports_data.provider.mapping import (
    map_clubs,
    map_competitions,
    map_fixtures,
    map_match_events,
    map_official_lineups,
    map_player_match_stats,
    map_seasons,
)
from sports_data.provider.models import ProviderSnapshot
from sports_data.provider.snapshots import store_provider_snapshot
from sports_data.provider.types import (
    MappedClub,
    MappedCompetition,
    MappedFixture,
    MappedLineupEntry,
    MappedMatchEvent,
    MappedOfficialLineup,
    MappedPlayerMatchStat,
    MappedSeason,
    ProviderEnvelope,
    ProviderPaging,
    ProviderRateLimit,
)

__all__ = [
    "ApiFootballClient",
    "MVP_LEAGUE_IDS",
    "MappedClub",
    "MappedCompetition",
    "MappedFixture",
    "MappedLineupEntry",
    "MappedMatchEvent",
    "MappedOfficialLineup",
    "MappedPlayerMatchStat",
    "MappedSeason",
    "PROVIDER_NAME",
    "ProviderAuthError",
    "ProviderConfigError",
    "ProviderEnvelope",
    "ProviderError",
    "ProviderHttpError",
    "ProviderPaging",
    "ProviderRateLimit",
    "ProviderRateLimitError",
    "ProviderResponseError",
    "ProviderSnapshot",
    "build_client_from_settings",
    "map_clubs",
    "map_competitions",
    "map_fixtures",
    "map_match_events",
    "map_official_lineups",
    "map_player_match_stats",
    "map_seasons",
    "merge_envelopes",
    "parse_envelope",
    "payload_sha256",
    "request_fingerprint",
    "store_provider_snapshot",
]
