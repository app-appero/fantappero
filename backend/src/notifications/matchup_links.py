"""Deep link al matchup H2H specifico per le notifiche di evento calciatore (TASK4).

Prima di questo modulo i template ``risultati.gol``/``risultati.assist``/...
puntavano sempre al percorso generico ``/turni`` (o ``/formazione`` per
infortunio/squalifica): chi riceveva la notifica doveva poi cercarsi lo
scontro giusto dentro la pagina Turni. Qui si risale, per singolo
destinatario, allo scontro H2H preciso in cui il suo fantasy team gioca
nella giornata della fixture che ha generato l'evento.

Formato del deep link, quando lo scontro si risolve:

    /turni/scontro/{slotId}

dove ``slotId`` è l'id di ``LeagueCalendarSlot`` (la riga ``league_calendar_
slots`` che modella uno scontro H2H). Non è una convenzione nuova: è lo
stesso path già registrato lato web in ``apps/web/src/routes/routeConfig.ts``
(route id ``matchday-matchup``, path ``/turni/scontro/:slotId``) usato dalla
pagina ``MatchupDetailPage``; lato mobile ``/turni*`` instrada già sulla tab
Turni (``apps/mobile/src/navigation/notificationDestination.ts``), così il
nuovo sottopercorso non rompe nulla anche prima che mobile implementi la
navigazione al singolo scontro.

Catena di risoluzione, dato (``team_id``, ``fixture_id``):

    FantasyTeam(team_id) -> league_id, membership_id
    FantasyRoundFixture(league_id, fixture_id) -> round_id
    FantasyRound(round_id) -> numero di turno europeo
    LeagueCalendar(league_id) -> calendario H2H della lega
    h2h_round_numbers_for_round(calendar, fantasy_round) -> giornate H2H ospitate
    LeagueCalendarSlot(calendar, quelle giornate, home/away membership == membership_id,
                        non bye) -> lo scontro

Se un pezzo della catena manca (lega senza calendario confermato, turno non
ancora mappato a una giornata H2H, fixture non collegata a nessun turno
europeo della lega, squadra a riposo quella giornata...) si torna al
percorso di fallback passato dal chiamante: mai un'eccezione, una notifica
non deve mai fallire per colpa del deep link.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.calendar_round_mapping import h2h_round_numbers_for_round
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from observability.logging import get_logger

logger = get_logger(__name__)

#: Percorso generico usato quando non si riesce a risalire allo scontro preciso.
DEFAULT_FALLBACK_DEEP_LINK = "/turni"


def matchup_deep_link(slot_id: UUID | str) -> str:
    """Formato canonico del deep link verso un singolo scontro H2H."""
    return f"/turni/scontro/{slot_id}"


def resolve_matchup_deep_link(
    session: Session,
    *,
    team_id: UUID,
    fixture_id: UUID | None,
    fallback: str = DEFAULT_FALLBACK_DEEP_LINK,
) -> str:
    """Deep link allo scontro H2H in cui ``team_id`` gioca nella giornata di ``fixture_id``.

    Ritorna sempre un percorso valido: ``fallback`` se manca un pezzo della
    catena lega -> turno -> giornata H2H -> scontro, mai un'eccezione.
    """
    if fixture_id is None:
        return fallback
    try:
        resolved = _resolve(session, team_id=team_id, fixture_id=fixture_id)
    except Exception:
        logger.warning("matchup_deep_link_resolution_failed", exc_info=True)
        return fallback
    return resolved if resolved is not None else fallback


def _resolve(session: Session, *, team_id: UUID, fixture_id: UUID) -> str | None:
    team = session.get(FantasyTeam, team_id)
    if team is None:
        return None

    round_fixture = session.scalar(
        select(FantasyRoundFixture).where(
            FantasyRoundFixture.league_id == team.league_id,
            FantasyRoundFixture.fixture_id == fixture_id,
            FantasyRoundFixture.excluded_at.is_(None),
        )
    )
    if round_fixture is None:
        return None

    fantasy_round = session.get(FantasyRound, round_fixture.round_id)
    if fantasy_round is None:
        return None

    calendar = session.scalar(
        select(LeagueCalendar).where(LeagueCalendar.league_id == team.league_id)
    )
    if calendar is None:
        return None

    h2h_round_numbers = h2h_round_numbers_for_round(
        session, calendar=calendar, fantasy_round=fantasy_round
    )
    if not h2h_round_numbers:
        return None

    slot = session.scalar(
        select(LeagueCalendarSlot).where(
            LeagueCalendarSlot.calendar_id == calendar.id,
            LeagueCalendarSlot.round_number.in_(h2h_round_numbers),
            LeagueCalendarSlot.is_bye.is_(False),
            or_(
                LeagueCalendarSlot.home_membership_id == team.membership_id,
                LeagueCalendarSlot.away_membership_id == team.membership_id,
            ),
        )
    )
    if slot is None:
        return None

    return matchup_deep_link(slot.id)
