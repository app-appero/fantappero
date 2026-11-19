"""Chi esce dalla rosa esce dalle formazioni dei turni non ancora iniziati (QA 19/11).

Il punteggio del turno (``compute_round_effective_lineups``, ``compute_round_results``) legge i
``LineupPlayer`` salvati senza guardare la rosa, e deve restare così: filtrare per la rosa di
oggi riscriverebbe la storia quando si ricalcola un turno passato. Perciò chi lascia una squadra
(scambio, svincolo, rimozione o sostituzione dell'admin, cambio in asta live o a buste) viene
tolto **nel momento in cui la lascia**, e solo dalla formazione e dalla bozza dei turni non
ancora iniziati: turno programmato o aperto, non omologato, e prima del primo blocco (nessuna
partita già in blocco, la stessa soglia per cui il mercato chiude, ``market.round_freeze``).
I turni bloccati o conclusi, e quindi chi ha la partita già iniziata, non si toccano.

- Titolari: la riga esce e il posto resta vuoto; gli altri tengono il loro ``sort_order`` (i
  titolari sono posizionali sul modulo), come la pulizia in lettura di GET formazione.
- Panchina: gli altri restano nell'ordine, con le posizioni ricompattate (0..n-1), così i primi
  ``BENCH_ACTIVE_SIZE`` sono gli stessi per il calcolo e per la pagina rosa.
- Bozza: ``""`` al posto del titolare, la panchina senza di lui.

È una pulizia di sistema, non una scelta del fantallenatore: nessuna nuova revisione,
``submitted_at`` e ``saved_at`` invariati, nessuna mossa tattica. Per ogni turno toccato resta
un evento di audit ``fantasy_lineup_saved`` con ``source = "roster_departure"`` e il nome del
calciatore; GET formazione lo usa per l'avviso «… non è più nella tua rosa» finché il
fantallenatore non salva di nuovo formazione o bozza (``departure_notices``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from database.enums import FantasyTurnStatus, LeagueAuditAction, LineupSlotKind
from fantasy_lineups.models import LineupDraft, LineupPlayer, LineupSubmission
from fantasy_lineups.rules import DEFAULT_LINEUP_LOCK_MARGIN_MINUTES
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.rules import STARTED_FIXTURE_STATUSES, derive_effective_status, ensure_utc
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from observability.context import get_correlation_id
from observability.logging import get_logger
from sports_data.fixtures.models import Fixture
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

#: ``details.source`` dell'evento di audit scritto dalla pulizia.
DEPARTURE_AUDIT_SOURCE = "roster_departure"
#: Stati in cui la formazione di un turno si pulisce ancora (se il turno non è iniziato).
_PURGEABLE_STATUSES = frozenset({FantasyTurnStatus.SCHEDULED, FantasyTurnStatus.OPEN})
#: Posizioni di appoggio per ricompattare la panchina senza violare l'unicità
#: ``(submission_id, slot_kind, sort_order)`` durante gli UPDATE.
_SORT_ORDER_PARKING = 10_000


@dataclass(frozen=True)
class DepartedLineupRemoval:
    """Un turno da cui il calciatore è stato tolto."""

    round_id: UUID
    #: Posto lasciato nella formazione salvata, ``("starter" | "bench", sort_order)``.
    lineup_slot: tuple[str, int] | None
    removed_from_draft: bool


@dataclass(frozen=True)
class DepartureNotice:
    """Calciatore tolto dalla formazione di un turno per l'uscita dalla rosa (dall'audit)."""

    athlete_id: str
    athlete_name: str
    removed_at: datetime


def is_purgeable_turn_status(status: FantasyTurnStatus) -> bool:
    return status in _PURGEABLE_STATUSES


def purge_departed_athlete_from_future_lineups(
    session: Session,
    *,
    league_id: UUID,
    team_id: UUID,
    athlete_id: UUID,
    now: datetime,
    actor_id: UUID | None = None,
) -> list[DepartedLineupRemoval]:
    """Toglie ``athlete_id`` da formazione e bozza di ``team_id`` nei turni non ancora iniziati.

    Va chiamata subito dopo aver liberato lo slot: lo fanno ``sync_ownership_on_release`` e
    ``sync_ownership_on_assign`` (fantasy_teams.ownership), da cui passano tutte le uscite
    dalla rosa. Se il calciatore è ancora nella rosa della squadra (lo stesso calciatore
    riassegnato) non fa niente. ``actor_id`` è chi ha fatto il cambio di rosa; senza, l'audit
    va al proprietario della squadra. Solo ``flush``: il commit resta al chiamante, nella
    stessa transazione del cambio di rosa.
    """
    # Le sessioni non fanno autoflush: lo slot appena liberato deve arrivare al DB prima di
    # chiedere se il calciatore è ancora in rosa.
    session.flush()
    still_owned = session.scalar(
        select(FantasyRosterSlot.id)
        .where(
            FantasyRosterSlot.fantasy_team_id == team_id,
            FantasyRosterSlot.athlete_id == athlete_id,
        )
        .limit(1)
    )
    if still_owned is not None:
        return []
    moment = ensure_utc(now)
    # Solo i turni in cui la squadra ha una formazione con lui o una bozza: il calendario può
    # avere molti turni programmati, e quasi tutti senza formazione.
    open_rounds = select(FantasyRound.id).where(
        FantasyRound.league_id == league_id,
        FantasyRound.status.in_(tuple(_PURGEABLE_STATUSES)),
        FantasyRound.homologated_at.is_(None),
    )
    fielded_in = (
        select(LineupSubmission.round_id)
        .join(LineupPlayer, LineupPlayer.submission_id == LineupSubmission.id)
        .where(
            LineupSubmission.fantasy_team_id == team_id,
            LineupSubmission.round_id.in_(open_rounds),
            LineupPlayer.athlete_id == athlete_id,
        )
    )
    drafted_in = select(LineupDraft.round_id).where(
        LineupDraft.fantasy_team_id == team_id,
        LineupDraft.round_id.in_(open_rounds),
    )
    candidates = list(
        session.scalars(
            select(FantasyRound)
            .where(or_(FantasyRound.id.in_(fielded_in), FantasyRound.id.in_(drafted_in)))
            .order_by(FantasyRound.number.asc())
        ).all()
    )
    if not candidates:
        return []
    margin = _lock_margin_minutes(session, league_id)
    rounds = [
        fantasy_round
        for fantasy_round in candidates
        if not _round_started(session, fantasy_round, now=moment, margin_minutes=margin)
    ]
    if not rounds:
        return []
    round_ids = [fantasy_round.id for fantasy_round in rounds]
    # Stesso ordine di blocco del salvataggio di formazione e bozza (prima la formazione, poi la
    # bozza); le righe si rileggono dopo il blocco, quindi un salvataggio concorrente già
    # concluso viene pulito anche lui.
    submissions = {
        row.round_id: row
        for row in session.scalars(
            select(LineupSubmission)
            .where(
                LineupSubmission.fantasy_team_id == team_id,
                LineupSubmission.round_id.in_(round_ids),
            )
            .options(selectinload(LineupSubmission.players))
            .with_for_update(of=LineupSubmission)
            .execution_options(populate_existing=True)
        ).all()
    }
    drafts = {
        row.round_id: row
        for row in session.scalars(
            select(LineupDraft)
            .where(
                LineupDraft.fantasy_team_id == team_id,
                LineupDraft.round_id.in_(round_ids),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
    }
    if not submissions and not drafts:
        return []

    removals: list[DepartedLineupRemoval] = []
    athlete_name: str | None = None
    audit_actor_id = actor_id
    for fantasy_round in rounds:
        submission = submissions.get(fantasy_round.id)
        draft = drafts.get(fantasy_round.id)
        lineup_slot = (
            _remove_from_submission(session, submission, athlete_id)
            if submission is not None
            else None
        )
        in_draft = _remove_from_draft(draft, athlete_id) if draft is not None else False
        if lineup_slot is None and not in_draft:
            continue
        removals.append(
            DepartedLineupRemoval(
                round_id=fantasy_round.id,
                lineup_slot=lineup_slot,
                removed_from_draft=in_draft,
            )
        )
        if athlete_name is None:
            athlete = session.get(Athlete, athlete_id)
            athlete_name = athlete.canonical_name if athlete is not None else ""
        if audit_actor_id is None:
            audit_actor_id = _team_owner_id(session, team_id)
        session.add(
            LeagueAuditEvent(
                league_id=league_id,
                # Chi ha fatto il cambio di rosa: la pulizia ne è una conseguenza.
                actor_id=audit_actor_id,
                action=LeagueAuditAction.FANTASY_LINEUP_SAVED,
                correlation_id=get_correlation_id(),
                details={
                    "source": DEPARTURE_AUDIT_SOURCE,
                    "roundId": str(fantasy_round.id),
                    "roundNumber": fantasy_round.number,
                    "fantasyTeamId": str(team_id),
                    "athleteId": str(athlete_id),
                    "athleteName": athlete_name,
                    "removedAt": moment.isoformat(),
                    "lineupSlotKind": lineup_slot[0] if lineup_slot is not None else None,
                    "lineupSortOrder": lineup_slot[1] if lineup_slot is not None else None,
                    "draft": in_draft,
                    "revision": submission.revision if submission is not None else None,
                    "tacticalMoveConsumed": False,
                },
            )
        )
    if removals:
        session.flush()
        logger.info(
            "fantasy_lineup_departed_athlete_removed",
            extra={"rounds": len(removals), "fantasy_team_id": str(team_id)},
        )
    return removals


def departure_notices(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    team_id: UUID,
) -> list[DepartureNotice]:
    """Chi è stato tolto dalla formazione o dalla bozza di questo turno, in ordine di uscita."""
    rows = session.scalars(
        select(LeagueAuditEvent.details)
        .where(
            LeagueAuditEvent.league_id == league_id,
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_SAVED,
            LeagueAuditEvent.details.contains(
                {
                    "source": DEPARTURE_AUDIT_SOURCE,
                    "roundId": str(round_id),
                    "fantasyTeamId": str(team_id),
                }
            ),
        )
        .order_by(LeagueAuditEvent.created_at.asc())
    ).all()
    notices: list[DepartureNotice] = []
    for details in rows:
        if not isinstance(details, dict):
            continue
        try:
            removed_at = ensure_utc(datetime.fromisoformat(str(details.get("removedAt"))))
        except ValueError:
            continue
        notices.append(
            DepartureNotice(
                athlete_id=str(details.get("athleteId") or ""),
                athlete_name=str(details.get("athleteName") or ""),
                removed_at=removed_at,
            )
        )
    notices.sort(key=lambda item: item.removed_at)
    return notices


def _remove_from_submission(
    session: Session, submission: LineupSubmission, athlete_id: UUID
) -> tuple[str, int] | None:
    leaving = next((row for row in submission.players if row.athlete_id == athlete_id), None)
    if leaving is None:
        return None
    slot = (leaving.slot_kind.value, leaving.sort_order)
    # delete-orphan: la riga esce davvero, prima di ricompattare (vincolo di unicità).
    submission.players.remove(leaving)
    session.flush()
    if leaving.slot_kind == LineupSlotKind.BENCH:
        bench = sorted(
            (row for row in submission.players if row.slot_kind == LineupSlotKind.BENCH),
            key=lambda row: row.sort_order,
        )
        moved = [(row, index) for index, row in enumerate(bench) if row.sort_order != index]
        if moved:
            for row, index in moved:
                row.sort_order = index + _SORT_ORDER_PARKING
            session.flush()
            for row, index in moved:
                row.sort_order = index
            session.flush()
    return slot


def _remove_from_draft(draft: LineupDraft, athlete_id: UUID) -> bool:
    key = str(athlete_id)
    starters = list(draft.starter_athlete_ids or [])
    bench = list(draft.bench_athlete_ids or [])
    new_starters = ["" if str(item) == key else item for item in starters]
    new_bench = [item for item in bench if str(item) != key]
    if new_starters == starters and new_bench == bench:
        return False
    # Liste nuove (non modificate sul posto): così SQLAlchemy vede il cambio del JSONB.
    draft.starter_athlete_ids = new_starters
    draft.bench_athlete_ids = new_bench
    return True


def _round_started(
    session: Session,
    fantasy_round: FantasyRound,
    *,
    now: datetime,
    margin_minutes: int,
) -> bool:
    """Primo blocco del turno raggiunto: stessa soglia di ``market.round_freeze``.

    Il turno conta come iniziato se il suo cutoff (primo calcio d'inizio) o una sua partita è
    entro il margine di blocco della lega, se una partita è già iniziata, o se il blocco di una
    partita è rimasto agganciato dopo un rinvio.
    """
    effective = derive_effective_status(
        fantasy_round.status, now=now, cutoff_at=fantasy_round.cutoff_at
    )
    if effective not in _PURGEABLE_STATUSES:
        return True
    first_lock = now + timedelta(minutes=margin_minutes)
    if fantasy_round.cutoff_at is not None and ensure_utc(fantasy_round.cutoff_at) <= first_lock:
        return True
    locked_fixture = session.scalar(
        select(FantasyRoundFixture.id)
        .join(Fixture, Fixture.id == FantasyRoundFixture.fixture_id)
        .where(
            FantasyRoundFixture.round_id == fantasy_round.id,
            FantasyRoundFixture.excluded_at.is_(None),
            or_(
                Fixture.kickoff_at <= first_lock,
                Fixture.status_short.in_(tuple(STARTED_FIXTURE_STATUSES)),
                FantasyRoundFixture.lock_latched_at.is_not(None),
            ),
        )
        .limit(1)
    )
    return locked_fixture is not None


def _team_owner_id(session: Session, team_id: UUID) -> UUID | None:
    return session.scalar(
        select(LeagueMembership.user_id)
        .join(FantasyTeam, FantasyTeam.membership_id == LeagueMembership.id)
        .where(FantasyTeam.id == team_id)
    )


def _lock_margin_minutes(session: Session, league_id: UUID) -> int:
    margin = session.scalar(
        select(LeagueRules.lineup_lock_margin_minutes).where(LeagueRules.league_id == league_id)
    )
    return margin if margin is not None else DEFAULT_LINEUP_LOCK_MARGIN_MINUTES


__all__ = [
    "DEPARTURE_AUDIT_SOURCE",
    "DepartedLineupRemoval",
    "DepartureNotice",
    "departure_notices",
    "is_purgeable_turn_status",
    "purge_departed_athlete_from_future_lineups",
]
