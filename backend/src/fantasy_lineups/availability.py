"""Chi di sicuro non prende il voto in un turno, per la formazione e per i job di sistema.

Estratto da ``FantasyLineupService`` (``_probable_hints``, ``_no_vote_reasons``) perché serve
anche fuori da un ``LeagueAccess``: la regola di inizio turno (``fantasy_lineups.turn_start``)
gira anche dal job del calcolo. Nessun cambio di comportamento rispetto all'originale.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from fantasy_lineups.kickoffs import KickoffRef
from fantasy_turns.models import FantasyRoundFixture
from fantasy_turns.rules import INACTIVE_FIXTURE_STATUSES
from observability.logging import get_logger
from sports_data.predicted.read import AthleteProbable, hints_for_fixtures

logger = get_logger(__name__)

__all__ = ["no_vote_reasons", "probable_hints"]


def probable_hints(
    session: Session,
    round_id: UUID,
    athlete_ids: list[UUID],
) -> dict[UUID, AthleteProbable]:
    """Indizi opzionali. Un errore qui non deve impedire di aprire la formazione."""
    try:
        with session.begin_nested():
            fixture_ids = list(
                session.scalars(
                    select(FantasyRoundFixture.fixture_id).where(
                        FantasyRoundFixture.round_id == round_id,
                        FantasyRoundFixture.excluded_at.is_(None),
                    )
                ).all()
            )
            return hints_for_fixtures(session, fixture_ids, athlete_ids)
    except Exception:
        logger.warning("probable_lineup_hints_unavailable", exc_info=True)
        return {}


def no_vote_reasons(
    athlete_ids: list[UUID],
    kickoffs: dict[UUID, KickoffRef],
    probable: dict[UUID, AthleteProbable],
    *,
    include_schedule: bool = True,
) -> dict[UUID, str]:
    """Chi di sicuro non prende il voto in questo turno, con il motivo da mostrare.

    Nessuna partita nel turno, partita rinviata o annullata, indisponibilità confermata.
    Non può entrare tra i titolari: altrimenti lo si schiera apposta per far entrare un
    panchinaro di cui si conosce già il voto.
    """
    reasons: dict[UUID, str] = {}
    for athlete_id in athlete_ids:
        ref = kickoffs.get(athlete_id)
        if include_schedule and ref is None:
            reasons[athlete_id] = "Nessuna partita in questo turno"
        elif (
            include_schedule
            and ref is not None
            and (ref.status_short or "").strip().upper() in INACTIVE_FIXTURE_STATUSES
        ):
            reasons[athlete_id] = "Partita rinviata o annullata"
        else:
            hint = probable.get(athlete_id)
            if hint is not None and hint.blocked:
                reasons[athlete_id] = hint.note
    return reasons
