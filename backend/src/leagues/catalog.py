"""MVP competition catalog (API-Football provider IDs, EP03-01)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CompetitionCatalogEntry:
    provider_id: int
    name: str
    country: str


MVP_COMPETITIONS: tuple[CompetitionCatalogEntry, ...] = (
    CompetitionCatalogEntry(provider_id=39, name="Premier League", country="England"),
    CompetitionCatalogEntry(provider_id=140, name="La Liga", country="Spain"),
    CompetitionCatalogEntry(provider_id=135, name="Serie A", country="Italy"),
    CompetitionCatalogEntry(provider_id=78, name="Bundesliga", country="Germany"),
    CompetitionCatalogEntry(provider_id=61, name="Ligue 1", country="France"),
)

MIN_LEAGUE_COMPETITIONS = 3
MAX_LEAGUE_COMPETITIONS = len(MVP_COMPETITIONS)
