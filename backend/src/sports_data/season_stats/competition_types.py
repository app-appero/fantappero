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
- tipo sconosciuto (elenco non ancora scaricato, competizione nuova, id ``0``) → esclusa.
"""

from __future__ import annotations

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
COMPETITION_TYPES = (COMPETITION_TYPE_LEAGUE, COMPETITION_TYPE_CUP)

_MVP = frozenset(MVP_LEAGUE_IDS)


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


def competition_kind(competition_provider_id: int, types: Mapping[int, str]) -> str:
    """``league``, ``cup`` o ``unknown`` (i 5 campionati sono sempre ``league``)."""
    if competition_provider_id in _MVP:
        return COMPETITION_TYPE_LEAGUE
    return types.get(competition_provider_id, COMPETITION_TYPE_UNKNOWN)


def is_championship(competition_provider_id: int, types: Mapping[int, str]) -> bool:
    """La riga conta nella media e nel Valore solo se è di un campionato."""
    return competition_kind(competition_provider_id, types) == COMPETITION_TYPE_LEAGUE


__all__ = [
    "COMPETITION_TYPES",
    "COMPETITION_TYPE_CUP",
    "COMPETITION_TYPE_LEAGUE",
    "COMPETITION_TYPE_UNKNOWN",
    "LEAGUES_ENDPOINT",
    "CompetitionTypeItem",
    "competition_kind",
    "is_championship",
    "load_competition_types",
    "parse_competition_types",
    "upsert_competition_types",
]
