"""Abbinamento giornata H2H ↔ turno europeo (EP13-P03).

Fino a EP07-05 l'abbinamento era implicito: ``FantasyRound.number ==
LeagueCalendarSlot.round_number``. Quel criterio conta anche le finestre sotto
soglia, che diventano turni ``skipped``: una giornata H2H abbinata a una di
quelle non è mai giocabile.

Dai calendari generati con l'ancoraggio alle finestre l'abbinamento è
esplicito e passa da ``league_calendar_round_windows``. I calendari
preesistenti non hanno quella mappatura e continuano a usare il criterio per
numero, così nessun dato storico cambia significato.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fantasy_turns.models import FantasyRound
from fantasy_turns.rules import ensure_utc
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarRoundWindow


def _window_key(start_at: datetime, end_at: datetime) -> tuple[datetime, datetime]:
    return ensure_utc(start_at), ensure_utc(end_at)


def rounds_by_h2h_number(
    session: Session,
    *,
    league_id: UUID,
    calendar: LeagueCalendar,
) -> dict[int, FantasyRound]:
    """Giornata H2H → turno europeo che la ospita."""
    rounds = list(
        session.scalars(select(FantasyRound).where(FantasyRound.league_id == league_id)).all()
    )
    mappings = list(calendar.round_windows)
    if not mappings:
        return {row.number: row for row in rounds}

    by_window = {_window_key(row.window_start_at, row.window_end_at): row for row in rounds}
    resolved: dict[int, FantasyRound] = {}
    for mapping in mappings:
        found = by_window.get(_window_key(mapping.window_start_at, mapping.window_end_at))
        if found is not None:
            resolved[mapping.round_number] = found
    return resolved


def round_for_h2h_number(
    session: Session,
    *,
    league_id: UUID,
    calendar: LeagueCalendar,
    round_number: int,
) -> FantasyRound | None:
    """Turno europeo di una singola giornata H2H."""
    return rounds_by_h2h_number(session, league_id=league_id, calendar=calendar).get(round_number)


def h2h_round_numbers_for_round(
    session: Session,
    *,
    calendar: LeagueCalendar,
    fantasy_round: FantasyRound,
) -> list[int]:
    """Giornate H2H ospitate da un turno europeo.

    Restituisce una lista perché il criterio è la finestra: senza mappatura
    esplicita resta l'unico numero progressivo corrispondente.
    """
    mappings = list(
        session.scalars(
            select(LeagueCalendarRoundWindow).where(
                LeagueCalendarRoundWindow.calendar_id == calendar.id
            )
        ).all()
    )
    if not mappings:
        return [fantasy_round.number]

    target = _window_key(fantasy_round.window_start_at, fantasy_round.window_end_at)
    return sorted(
        mapping.round_number
        for mapping in mappings
        if _window_key(mapping.window_start_at, mapping.window_end_at) == target
    )
