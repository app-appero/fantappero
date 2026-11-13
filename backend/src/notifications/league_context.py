"""Contesto lega per le notifiche del mercato (id e nome nel testo e nel link)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from leagues.models.league import League


def league_params(session: Session, league_id: UUID) -> dict[str, object]:
    """``league_id`` e ``league_name`` da mettere nei parametri di una notifica."""
    league = session.get(League, league_id)
    params: dict[str, object] = {"league_id": str(league_id)}
    if league is not None:
        params["league_name"] = league.name
    return params
