"""Campionato o coppa: quali righe dello storico contano nella media e nel Valore (1.3).

Decisione di Rosario (22/11): la media stagionale e il Valore di mercato contano **solo le
righe di campionato**; le coppe (Champions League, coppe nazionali, supercoppe…) restano
visibili nella carriera del calciatore ma non entrano nei conti.

Il tipo di ogni competizione viene dal fornitore con **una sola chiamata**: ``/leagues`` senza
filtri restituisce tutte le competizioni, ognuna con ``league{id, name, type}`` (``"League"`` o
``"Cup"``), senza paginazione. Si salva in ``provider_competition_types`` come primo passo
dell'import dello storico (``provider_import``). Con ``type=cup`` si saprebbe solo quali sono
coppe e i campionati fuori dai 5 (Serie B, Eredivisie…) resterebbero sconosciuti, quindi
esclusi: per questo la chiamata è senza filtro.

Regola (``is_championship``):

- competizione dei 5 campionati di ``MVP_LEAGUE_IDS`` → campionato, sempre;
- tipo noto ``league`` → campionato;
- tipo noto ``cup`` → coppa, esclusa;
- tipo sconosciuto (elenco non ancora scaricato, competizione nuova, id ``0``) → esclusa;
- giovanili, riserve e femminili (``is_youth_or_reserve``) → escluse anche se il fornitore le
  dà come ``league`` (QA notte 24-25/11: K. Braithwaite con 7,3 di media dalla sola UEFA Youth
  League). Restano nella carriera.

Giovanili e riserve (``COMPETITION_TYPE_YOUTH``), elenco volutamente prudente: si guarda il
**nome della competizione** (``_YOUTH_COMPETITION``: «Youth», U14–U23 / «Under 21» / «Sub-20»,
«Primavera», «Reserve»/«Reserves», «Juvenil», «Junioren», «Premier League 2», «Professional
Development League», competizioni femminili) e il **nome della squadra** (``_RESERVE_TEAM``:
seconde squadre «… II», «… B», «… U23», «… Reserves», «… Next Gen», «Jong …»), perché le seconde
squadre giocano in campionati senior (3. Liga, Primera Federación, Serie C, Eerste Divisie). Un
«II» o una «B» nel nome della competizione non basta: «Liga II» e «Primera B» sono campionati
senior. I 5 campionati di ``MVP_LEAGUE_IDS`` contano sempre.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from sports_data.provider.constants import MVP_LEAGUE_IDS
from sports_data.provider.types import ProviderEnvelope
from sports_data.season_stats.models import ProviderCompetitionType

LEAGUES_ENDPOINT = "/leagues"

COMPETITION_TYPE_LEAGUE = "league"
COMPETITION_TYPE_CUP = "cup"
#: Non è un valore della tabella: competizione assente dall'elenco del fornitore.
COMPETITION_TYPE_UNKNOWN = "unknown"
#: Non è un valore della tabella: giovanili, riserve o femminili, dal nome (25/11).
COMPETITION_TYPE_YOUTH = "youth"
COMPETITION_TYPES = (COMPETITION_TYPE_LEAGUE, COMPETITION_TYPE_CUP)

_MVP = frozenset(MVP_LEAGUE_IDS)

_YOUTH_COMPETITION = re.compile(
    r"\byouth\b"
    r"|\bu-?(?:1[4-9]|2[0-3])\b"
    r"|\bunder[- ]?(?:1[4-9]|2[0-3])\b"
    r"|\bsub[- ]?(?:1[4-9]|2[0-3])\b"
    r"|\bprimavera\b"
    r"|\breserves?\b"
    r"|\bjuvenil\b"
    r"|\bjunioren\b"
    r"|\bpremier league 2\b"
    r"|\bprofessional development league\b"
    r"|\bwomen\b|\bwomen's\b|\bfemminile\b|\bf[eé]minine\b|\bfemenin[ao]\b"
    r"|\bfeminin[ao]\b|\bfrauen\b|\bwsl\b",
    re.IGNORECASE,
)
_RESERVE_TEAM = re.compile(
    r"\s(?:II|B|U-?(?:1[4-9]|2[0-3])|Reserves?|Next Gen)$|^Jong\s",
)


@dataclass(frozen=True)
class CompetitionTypeItem:
    provider_id: int
    type: str
    name: str | None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_competition_types(envelope: ProviderEnvelope) -> list[CompetitionTypeItem]:
    """Tipi da una risposta ``/leagues`` (``league.type``: ``"League"`` o ``"Cup"``)."""
    items: dict[int, CompetitionTypeItem] = {}
    for entry in envelope.response:
        if not isinstance(entry, dict):
            continue
        league = entry.get("league")
        if not isinstance(league, dict):
            continue
        provider_id = _as_int(league.get("id"))
        raw_type = league.get("type")
        if provider_id is None or provider_id <= 0 or not isinstance(raw_type, str):
            continue
        kind = raw_type.strip().lower()
        if kind not in COMPETITION_TYPES:
            continue
        name = league.get("name")
        items[provider_id] = CompetitionTypeItem(
            provider_id=provider_id,
            type=kind,
            name=name.strip()[:120] if isinstance(name, str) and name.strip() else None,
        )
    return list(items.values())


def upsert_competition_types(
    session: Session,
    items: Iterable[CompetitionTypeItem],
    *,
    fetched_at: datetime,
    snapshot_id: UUID | None,
) -> int:
    """Upsert sull'id del fornitore; ritorna le righe scritte."""
    values = [
        {
            "provider_id": item.provider_id,
            "type": item.type,
            "name": item.name,
            "snapshot_id": snapshot_id,
            "fetched_at": fetched_at,
        }
        for item in items
    ]
    if not values:
        return 0
    stmt = insert(ProviderCompetitionType).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProviderCompetitionType.provider_id],
        set_={
            "type": stmt.excluded.type,
            "name": stmt.excluded.name,
            "snapshot_id": stmt.excluded.snapshot_id,
            "fetched_at": stmt.excluded.fetched_at,
            "updated_at": func.timezone("utc", func.now()),
        },
    )
    session.execute(stmt)
    return len(values)


def load_competition_types(session: Session) -> dict[int, str]:
    """Tutto l'elenco (circa 1.200 competizioni): id del fornitore → ``league``/``cup``."""
    return {
        int(provider_id): str(kind)
        for provider_id, kind in session.execute(
            select(ProviderCompetitionType.provider_id, ProviderCompetitionType.type)
        ).tuples()
    }


def is_youth_or_reserve(competition_name: str | None, club_name: str | None = None) -> bool:
    """Competizione giovanile, di riserve o femminile, o seconda squadra (vedi il modulo)."""
    if competition_name and _YOUTH_COMPETITION.search(competition_name):
        return True
    return bool(club_name and _RESERVE_TEAM.search(club_name.strip()))


def competition_kind(
    competition_provider_id: int,
    types: Mapping[int, str],
    *,
    competition_name: str | None = None,
    club_name: str | None = None,
) -> str:
    """``league``, ``cup``, ``youth`` o ``unknown`` (i 5 campionati sono sempre ``league``)."""
    if competition_provider_id in _MVP:
        return COMPETITION_TYPE_LEAGUE
    if is_youth_or_reserve(competition_name, club_name):
        return COMPETITION_TYPE_YOUTH
    return types.get(competition_provider_id, COMPETITION_TYPE_UNKNOWN)


def is_championship(
    competition_provider_id: int,
    types: Mapping[int, str],
    *,
    competition_name: str | None = None,
    club_name: str | None = None,
) -> bool:
    """La riga conta nella media e nel Valore solo se è di un campionato senior."""
    return (
        competition_kind(
            competition_provider_id,
            types,
            competition_name=competition_name,
            club_name=club_name,
        )
        == COMPETITION_TYPE_LEAGUE
    )


__all__ = [
    "COMPETITION_TYPES",
    "COMPETITION_TYPE_CUP",
    "COMPETITION_TYPE_LEAGUE",
    "COMPETITION_TYPE_UNKNOWN",
    "COMPETITION_TYPE_YOUTH",
    "LEAGUES_ENDPOINT",
    "CompetitionTypeItem",
    "competition_kind",
    "is_championship",
    "is_youth_or_reserve",
    "load_competition_types",
    "parse_competition_types",
    "upsert_competition_types",
]
