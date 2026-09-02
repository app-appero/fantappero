"""Pannello operatore: turni, calendario, formazioni IA (EP-turni-automazione).

Le azioni sui turni erano finora esclusiva dell'admin di lega. Apertura,
ricalcolo cutoff, generazione calendario e formazioni IA sono ormai
automatiche (cron periodici + apertura alla omologazione del turno
precedente): questo modulo espone all'operatore di piattaforma le stesse
primitive già esistenti, come override manuale — sia massivo (tutte le
leghe attive) sia puntuale (una lega/turno specifico, tramite gli endpoint
già esistenti in `fantasy_turns.router`/`fantasy_lineups.router`, ora
protetti da `Permission.GLOBAL_OPERATE` invece di `LEAGUE_ADMIN`).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from admin.schemas import AdminLeagueTurnStatusResponse
from database.enums import FantasyTurnStatus, LeagueState
from fantasy_turns.models import FantasyRound
from leagues.models.league import League
from leagues.models.league_calendar import LeagueCalendar

#: Ordine di preferenza per scegliere il "turno corrente" da mostrare
#: all'operatore: un turno aperto prevale su uno programmato, che prevale
#: su uno bloccato/omologato (fine stagione o fra un turno e l'altro).
_STATUS_PRIORITY = {
    FantasyTurnStatus.OPEN: 0,
    FantasyTurnStatus.SCHEDULED: 1,
    FantasyTurnStatus.LOCKED: 2,
    FantasyTurnStatus.SKIPPED: 3,
}


def _pick_current_round(rounds: list[FantasyRound]) -> FantasyRound | None:
    if not rounds:
        return None
    open_or_scheduled = [
        r for r in rounds if r.status in (FantasyTurnStatus.OPEN, FantasyTurnStatus.SCHEDULED)
    ]
    if open_or_scheduled:
        return min(
            open_or_scheduled,
            key=lambda r: (_STATUS_PRIORITY[r.status], r.number),
        )
    return max(rounds, key=lambda r: r.number)


def list_league_turn_status(session: Session) -> list[AdminLeagueTurnStatusResponse]:
    """Elenco leghe attive con turno corrente e stato, per la scelta operatore.

    Query pragmatica in due passi (leghe, poi tutti i loro turni) invece di
    una query aggregata: il volume atteso (leghe attive) è basso e questa
    lettura serve solo a orientare un intervento manuale, non è un percorso
    critico per latenza.
    """
    leagues = list(
        session.scalars(
            select(League).where(League.state == LeagueState.ACTIVE).order_by(League.name.asc())
        ).all()
    )
    if not leagues:
        return []
    league_ids = [league.id for league in leagues]

    rounds_by_league: dict[object, list[FantasyRound]] = {}
    for row in session.scalars(
        select(FantasyRound)
        .where(FantasyRound.league_id.in_(league_ids))
        .order_by(FantasyRound.league_id.asc(), FantasyRound.number.asc())
    ).all():
        rounds_by_league.setdefault(row.league_id, []).append(row)

    calendar_updated_by_league: dict[object, datetime] = {
        row.league_id: row.generated_at
        for row in session.scalars(
            select(LeagueCalendar).where(LeagueCalendar.league_id.in_(league_ids))
        ).all()
    }

    results: list[AdminLeagueTurnStatusResponse] = []
    for league in leagues:
        current = _pick_current_round(rounds_by_league.get(league.id, []))
        results.append(
            AdminLeagueTurnStatusResponse(
                league_id=str(league.id),
                league_name=league.name,
                current_round_id=str(current.id) if current else None,
                current_round_number=current.number if current else None,
                current_round_status=current.status.value if current else None,
                homologation_status=(
                    current.homologation_status.value if current else None
                ),
                calendar_updated_at=calendar_updated_by_league.get(league.id),
            )
        )
    return results
