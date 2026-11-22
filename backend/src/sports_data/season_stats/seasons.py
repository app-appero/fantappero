"""Stagioni dello storico: etichette («25/26») e stagioni passate da importare."""

from __future__ import annotations

#: Quante stagioni passate si scaricano dal fornitore (decisione di Rosario, 22/11):
#: con la stagione 2026/27 in corso sono la 2024/25 e la 2025/26.
PAST_SEASONS_FROM_PROVIDER = 2

SOURCE_PROVIDER = "provider"
SOURCE_FANTAPPERO = "fantappero"
SEASON_STAT_SOURCES = (SOURCE_PROVIDER, SOURCE_FANTAPPERO)

#: Club o competizione senza id del fornitore (la colonna è parte della chiave unica).
UNKNOWN_PROVIDER_ID = 0


def season_label(season_year: int) -> str:
    """``2025`` → ``"25/26"`` (anno del fornitore = anno d'inizio della stagione)."""
    return f"{season_year % 100:02d}/{(season_year + 1) % 100:02d}"


def past_seasons(
    current_season_year: int, *, count: int = PAST_SEASONS_FROM_PROVIDER
) -> tuple[int, ...]:
    """Le ``count`` stagioni concluse prima di quella in corso, la più recente per prima.

    ``past_seasons(2026)`` → ``(2025, 2024)``.
    """
    return tuple(current_season_year - offset for offset in range(1, count + 1))


def career_seasons(current_season_year: int) -> tuple[int, ...]:
    """Stagioni della scheda calciatore: quella in corso e le due precedenti, dalla più recente."""
    return (current_season_year, *past_seasons(current_season_year))
