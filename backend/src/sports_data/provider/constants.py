"""API-Football v3 constants (SPD adapter — EP04-01)."""

from __future__ import annotations

PROVIDER_NAME = "api-football-v3"
DEFAULT_BASE_URL = "https://v3.football.api-sports.io"
AUTH_HEADER = "x-apisports-key"

# Five MVP competitions (provider league ids) — catalog sync EP04-02.
MVP_LEAGUE_IDS: tuple[int, ...] = (39, 140, 135, 78, 61)

# Endpoints in EP00-01 scope that the adapter may call.
KNOWN_ENDPOINTS: frozenset[str] = frozenset(
    {
        "/leagues",
        "/teams",
        "/players",
        "/players/squads",
        "/fixtures",
        "/fixtures/events",
        "/fixtures/lineups",
        "/fixtures/players",
        "/injuries",
        "/transfers",
        "/standings",
        "/predictions",
        "/status",
    }
)
