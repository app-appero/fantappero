"""Lega al completo: il mercato si apre solo a posti tutti occupati (decisione del 20/11/2026).

Una lega è «al completo» quando gli iscritti (``league_memberships``) sono quanti i
partecipanti del regolamento (``league_rules.participant_count``). Gli inviti in attesa non
contano: il posto è occupato solo da chi è entrato.

Finché la lega non è al completo restano chiusi l'inserimento in rosa fatto dal partecipante,
le aste (buste chiuse, a rilanci, svincolati) e gli scambi. È l'unico punto che fa il conto:
lo usano il controllo del mercato (``market.gate``), l'interruttore dell'amministratore, le
risposte per le app e l'avviso «La lega è al completo».

Gli inviti nominativi in attesa (non scaduti, senza risposta) tengono però un posto: chi entra
con link o codice non lo prende (``invite_service``), e l'amministratore non ne manda altri
(``named_invite_service``). Per questo le app li mostrano accanto al conto, «3/4 · 1 invito in
attesa» (Rosario, 20/11): la regola è una sola, ``pending_named_invite_count``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import NamedInviteStatus
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.models.named_league_invite import NamedLeagueInvite

LEAGUE_NOT_FULL_CODE = "league_not_full"


@dataclass(frozen=True, slots=True)
class LeagueOccupancy:
    """Iscritti e partecipanti previsti dal regolamento (``None`` senza regolamento).

    ``pending_invites`` sono gli inviti nominativi che tengono un posto: si mostrano accanto al
    conto ma non rendono la lega al completo.
    """

    members: int
    participants: int | None
    pending_invites: int = 0

    @property
    def is_full(self) -> bool:
        # Senza regolamento non c'è un numero di posti da riempire: la lega non è al completo.
        return self.participants is not None and self.members >= self.participants


def pending_named_invite_count(
    session: Session, league_id: UUID, *, now: datetime | None = None
) -> int:
    """Inviti nominativi della lega che tengono un posto: in attesa di risposta e non scaduti.

    È la regola con cui l'ingresso con link o codice (``invite_service``) e un nuovo invito
    nominativo (``named_invite_service``) contano i posti riservati.
    """
    moment = now if now is not None else datetime.now(UTC)
    return (
        session.scalar(
            select(func.count(NamedLeagueInvite.id)).where(
                NamedLeagueInvite.league_id == league_id,
                NamedLeagueInvite.status == NamedInviteStatus.PENDING,
                NamedLeagueInvite.expires_at > moment,
            )
        )
        or 0
    )


def league_occupancy(
    session: Session, league_id: UUID, *, include_pending: bool = True
) -> LeagueOccupancy:
    members = (
        session.scalar(
            select(func.count(LeagueMembership.id)).where(LeagueMembership.league_id == league_id)
        )
        or 0
    )
    participants = session.scalar(
        select(LeagueRules.participant_count).where(LeagueRules.league_id == league_id)
    )
    pending = pending_named_invite_count(session, league_id) if include_pending else 0
    return LeagueOccupancy(members=members, participants=participants, pending_invites=pending)


def league_is_full(session: Session, league_id: UUID) -> bool:
    """True quando ogni posto della lega è occupato da un iscritto."""
    return league_occupancy(session, league_id, include_pending=False).is_full


def pending_invites_label(count: int) -> str:
    """«1 invito in attesa», «2 inviti in attesa»."""
    return f"{count} invito in attesa" if count == 1 else f"{count} inviti in attesa"


def league_not_full_message(occupancy: LeagueOccupancy) -> str:
    """«Il mercato si apre quando la lega è al completo (3/4 partecipanti · 1 invito in attesa).»

    Gli inviti in attesa compaiono solo se ce ne sono.
    """
    participants = occupancy.participants if occupancy.participants is not None else "?"
    pending = (
        f" · {pending_invites_label(occupancy.pending_invites)}"
        if occupancy.pending_invites > 0
        else ""
    )
    return (
        "Il mercato si apre quando la lega è al completo "
        f"({occupancy.members}/{participants} partecipanti{pending})."
    )


def assert_league_full_for_market(session: Session, league_id: UUID) -> None:
    """Blocca l'attività di mercato finché la lega non è al completo (400 ``league_not_full``)."""
    occupancy = league_occupancy(session, league_id, include_pending=False)
    if not occupancy.is_full:
        # Il conto degli inviti in attesa serve solo al messaggio.
        occupancy = league_occupancy(session, league_id)
        raise ValidationAuthError(league_not_full_message(occupancy), code=LEAGUE_NOT_FULL_CODE)
