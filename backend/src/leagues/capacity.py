"""Lega al completo: il mercato si apre solo a posti tutti occupati (decisione del 20/11/2026).

Una lega è «al completo» quando gli iscritti (``league_memberships``) sono quanti i
partecipanti del regolamento (``league_rules.participant_count``). Gli inviti in attesa non
contano: il posto è occupato solo da chi è entrato.

Finché la lega non è al completo restano chiusi l'inserimento in rosa fatto dal partecipante,
le aste (buste chiuse, a rilanci, svincolati) e gli scambi. È l'unico punto che fa il conto:
lo usano il controllo del mercato (``market.gate``), l'interruttore dell'amministratore, le
risposte per le app e l'avviso «La lega è al completo».
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules

LEAGUE_NOT_FULL_CODE = "league_not_full"


@dataclass(frozen=True, slots=True)
class LeagueOccupancy:
    """Iscritti e partecipanti previsti dal regolamento (``None`` senza regolamento)."""

    members: int
    participants: int | None

    @property
    def is_full(self) -> bool:
        # Senza regolamento non c'è un numero di posti da riempire: la lega non è al completo.
        return self.participants is not None and self.members >= self.participants


def league_occupancy(session: Session, league_id: UUID) -> LeagueOccupancy:
    members = (
        session.scalar(
            select(func.count(LeagueMembership.id)).where(LeagueMembership.league_id == league_id)
        )
        or 0
    )
    participants = session.scalar(
        select(LeagueRules.participant_count).where(LeagueRules.league_id == league_id)
    )
    return LeagueOccupancy(members=members, participants=participants)


def league_is_full(session: Session, league_id: UUID) -> bool:
    """True quando ogni posto della lega è occupato da un iscritto."""
    return league_occupancy(session, league_id).is_full


def league_not_full_message(occupancy: LeagueOccupancy) -> str:
    participants = occupancy.participants if occupancy.participants is not None else "?"
    return (
        "Il mercato si apre quando la lega è al completo "
        f"({occupancy.members}/{participants} partecipanti)."
    )


def assert_league_full_for_market(session: Session, league_id: UUID) -> None:
    """Blocca l'attività di mercato finché la lega non è al completo (400 ``league_not_full``)."""
    occupancy = league_occupancy(session, league_id)
    if not occupancy.is_full:
        raise ValidationAuthError(league_not_full_message(occupancy), code=LEAGUE_NOT_FULL_CODE)
