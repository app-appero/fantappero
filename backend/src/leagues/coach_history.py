"""Storico fantallenatore: solo fatti osservabili (EP13-P06).

Motore puro, senza sessione né I/O.

La card vieta esplicitamente le etichette interpretative — «offensivo»,
«prudente» — finché metrica, campione minimo e spiegabilità non sono
documentati. Qui si contano piazzamenti in leghe **concluse**, nient'altro:
ogni numero è ricostruibile da `league_standings` e da `League.state`.

Il nome della lega non compare mai. Un amministratore che consulta la
directory non deve poter dedurre a quali leghe private altrui una persona
partecipa: restano posizione, numero di partecipanti e stagione.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConcludedPlacement:
    """Piazzamento in una lega conclusa, senza identificarla."""

    season_year: int
    position: int
    participant_count: int
    played: int
    points: int
    fantasy_points: float


@dataclass(frozen=True)
class CoachHistory:
    """Riepilogo deterministico dello storico."""

    concluded_leagues: int
    best_position: int | None
    placements: tuple[ConcludedPlacement, ...]

    @property
    def has_history(self) -> bool:
        return self.concluded_leagues > 0


def build_history(placements: Iterable[ConcludedPlacement]) -> CoachHistory:
    """Aggrega i piazzamenti in ordine cronologico decrescente.

    Ordinamento deterministico: stagione più recente prima, poi posizione,
    poi numero di partecipanti. A parità di input l'output è identico.
    """
    ordered = sorted(
        placements,
        key=lambda item: (-item.season_year, item.position, item.participant_count),
    )
    if not ordered:
        return CoachHistory(concluded_leagues=0, best_position=None, placements=())
    return CoachHistory(
        concluded_leagues=len(ordered),
        best_position=min(item.position for item in ordered),
        placements=tuple(ordered),
    )


def seniority_label(created_at: datetime | None, *, now: datetime) -> str | None:
    """Anzianità in forma «mese/anno», mai una data esatta.

    Il giorno preciso di iscrizione è un dato personale che non serve a
    valutare un fantallenatore: basta sapere da quanto è sulla piattaforma.
    """
    if created_at is None:
        return None
    if created_at > now:
        # Orologi disallineati: meglio nessuna informazione che una futura.
        return None
    return f"{created_at.month:02d}/{created_at.year}"


def summary_line(history: CoachHistory) -> str:
    """Riga sintetica per la preview, neutra quando lo storico è vuoto.

    Chi non ha ancora concluso leghe è semplicemente nuovo: uno «0» accanto
    al nome si leggerebbe come un giudizio negativo.
    """
    if not history.has_history:
        return "Nessuna lega conclusa"
    leagues = "lega conclusa" if history.concluded_leagues == 1 else "leghe concluse"
    best = history.best_position
    if best is None:
        return f"{history.concluded_leagues} {leagues}"
    return f"{history.concluded_leagues} {leagues} · miglior {best}º"


def placements_page(
    placements: Sequence[ConcludedPlacement],
    *,
    page: int,
    page_size: int,
) -> tuple[tuple[ConcludedPlacement, ...], int]:
    """Pagina i piazzamenti; restituisce anche il totale."""
    total = len(placements)
    if page < 1 or page_size < 1:
        return (), total
    start = (page - 1) * page_size
    return tuple(placements[start : start + page_size]), total
