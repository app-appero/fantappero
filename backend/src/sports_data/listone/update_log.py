"""Scrittura e lettura del registro degli aggiornamenti del listone (release 1.4).

Ogni aggiornamento riuscito lascia una riga in ``listone_updates`` (vedi ``update_models``):
la scrive chi aggiorna, nella stessa transazione delle modifiche al listone, così una riga
c'è solo se l'aggiornamento è stato salvato davvero.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from sports_data.listone.update_models import (
    LISTONE_UPDATE_KINDS,
    LISTONE_UPDATE_SOURCES,
    ListoneUpdate,
)

_NAME_MAX = 120


def _clip(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text[:_NAME_MAX] if text else None


def record_listone_update(
    session: Session,
    *,
    season_year: int,
    kind: str,
    source: str,
    actor: object | None = None,
    league: object | None = None,
    added: int = 0,
    removed: int = 0,
    changed: int = 0,
) -> ListoneUpdate:
    """Aggiunge la riga dell'aggiornamento (senza flush: lo fa chi salva il listone).

    ``actor`` e ``league`` sono l'utente e la lega (o oggetti con ``id`` e ``display_name`` /
    ``name``): il nome si copia nella riga e resta anche se l'account o la lega spariscono.
    """
    if kind not in LISTONE_UPDATE_KINDS:
        raise ValueError(f"listone update kind sconosciuto: {kind}")
    if source not in LISTONE_UPDATE_SOURCES:
        raise ValueError(f"listone update source sconosciuta: {source}")
    actor_id = getattr(actor, "id", None) if actor is not None else None
    league_id = getattr(league, "id", None) if league is not None else None
    row = ListoneUpdate(
        season_year=season_year,
        kind=kind,
        source=source,
        actor_id=actor_id if isinstance(actor_id, UUID) else None,
        actor_display_name=_clip(_display_name(actor)),
        league_id=league_id if isinstance(league_id, UUID) else None,
        league_name=_clip(getattr(league, "name", None)) if league is not None else None,
        added=max(0, int(added)),
        removed=max(0, int(removed)),
        changed=max(0, int(changed)),
    )
    session.add(row)
    return row


def latest_listone_update(session: Session) -> ListoneUpdate | None:
    """L'ultimo aggiornamento registrato, di qualsiasi stagione."""
    return session.scalars(
        select(ListoneUpdate)
        .order_by(ListoneUpdate.created_at.desc(), ListoneUpdate.id.desc())
        .limit(1)
    ).first()


def _display_name(actor: object | None) -> str | None:
    if actor is None:
        return None
    try:
        name = getattr(actor, "display_name", None)
    except Exception:  # noqa: BLE001 — un profilo non caricato non deve fermare il salvataggio
        return None
    return name if isinstance(name, str) else None
