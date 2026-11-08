"""Mercato chiuso a turno in corso (decisione del 08/11/2026).

Dal primo blocco del turno (primo calcio d'inizio meno il margine di lega) fino
all'omologazione non si eseguono scambi né movimenti di rosa. Le formazioni del turno
restano quelle salvate: se un giocatore cambiasse squadra a metà turno potrebbe contare per
due squadre, o lasciare un posto vuoto da riempire con un panchinaro di cui si conosce già il
voto.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from auth.exceptions import ValidationAuthError
from database.enums import FantasyTurnStatus
from fantasy_lineups.rules import DEFAULT_LINEUP_LOCK_MARGIN_MINUTES
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.rules import STARTED_FIXTURE_STATUSES
from leagues.models.league_rules import LeagueRules
from sports_data.fixtures.models import Fixture

ROUND_IN_PROGRESS_CODE = "market_round_in_progress"
ROUND_IN_PROGRESS_MESSAGE = (
    "Mercato e scambi sono chiusi durante il turno in corso: riaprono a calcolo concluso."
)
#: Un turno mai omologato per un problema di dati non tiene chiuso il mercato per sempre.
STUCK_ROUND_GRACE = timedelta(days=7)


def league_round_in_progress(
    session: Session, league_id: UUID, *, now: datetime | None = None
) -> FantasyRound | None:
    """Il turno della lega iniziato e non ancora omologato, se c'è."""
    moment = now or datetime.now(UTC)
    margin = session.scalar(
        select(LeagueRules.lineup_lock_margin_minutes).where(LeagueRules.league_id == league_id)
    )
    margin_minutes = margin if margin is not None else DEFAULT_LINEUP_LOCK_MARGIN_MINUTES
    first_lock = moment + timedelta(minutes=margin_minutes)
    # Non solo la data del turno: anche una sua partita già iniziata o in blocco basta, nel
    # caso l'orario sia stato anticipato e il turno non sia ancora stato riallineato.
    started_rounds = (
        select(FantasyRoundFixture.round_id)
        .join(Fixture, Fixture.id == FantasyRoundFixture.fixture_id)
        .where(
            FantasyRoundFixture.excluded_at.is_(None),
            or_(
                Fixture.kickoff_at <= first_lock,
                Fixture.status_short.in_(tuple(STARTED_FIXTURE_STATUSES)),
            ),
        )
    )
    return session.scalars(
        select(FantasyRound)
        .where(
            FantasyRound.league_id == league_id,
            FantasyRound.status.in_((FantasyTurnStatus.OPEN, FantasyTurnStatus.LOCKED)),
            FantasyRound.homologated_at.is_(None),
            FantasyRound.window_end_at >= moment - STUCK_ROUND_GRACE,
            or_(FantasyRound.cutoff_at <= first_lock, FantasyRound.id.in_(started_rounds)),
        )
        .order_by(FantasyRound.number)
    ).first()


def assert_no_round_in_progress(session: Session, league_id: UUID) -> None:
    if league_round_in_progress(session, league_id) is not None:
        raise ValidationAuthError(ROUND_IN_PROGRESS_MESSAGE, code=ROUND_IN_PROGRESS_CODE)
