"""Regola di inizio turno per le formazioni (decisione di Rosario del 19/11).

All'inizio del turno (il primo blocco: primo calcio d'inizio meno il margine di lega, la stessa
soglia di ``market.round_freeze`` e di ``fantasy_lineups.departures``) ogni formazione salvata:

1. perde chi non è più nella rosa della squadra: il posto da titolare resta vuoto, la panchina
   si ricompatta, come la pulizia all'uscita dalla rosa (``departures``). Vale anche per le
   formazioni rimaste sporche da prima di quella pulizia;
2. copre i posti vuoti tra i titolari: entra il primo della panchina attiva con il ruolo del
   posto, e il suo posto in panchina lo prende il primo della tribuna con lo stesso ruolo;
   senza nessuno in panchina entra direttamente il primo della tribuna; senza nessuno di quel
   ruolo il posto resta vuoto (``rules.fill_lineup_holes_at_turn_start``).

Come la pulizia all'uscita è una regola di sistema, non una scelta del fantallenatore: nessuna
nuova revisione, ``submitted_at`` invariato, nessuna mossa tattica. Per ogni formazione cambiata
resta un evento di audit ``fantasy_lineup_saved`` con ``source = "turn_start_autofill"`` e chi
è andato dove; GET formazione lo usa per l'avviso («All'inizio del turno …») finché il
fantallenatore non salva di nuovo (``turn_start_notices``).

Quando gira, sempre prima di ogni calcolo e sempre la stessa regola:

- dal job del calcolo (``fantasy_turns.live_pipeline.process_live_fantasy_rounds``, ogni minuto
  con lo scheduler dei dati sportivi): i turni appena arrivati al primo blocco
  (``settle_started_turns``);
- dentro ``compute_round_effective_lineups``, prima di leggere le formazioni: nessun calcolo
  parte da una formazione non sistemata, anche dai comandi manuali dell'operatore. Le formazioni
  automatiche create a fine turno passano anche loro di qui;
- da GET, salvataggio e bozza della formazione dopo il primo blocco, per la squadra che la apre
  (insieme alla formazione automatica del primo blocco, ``FantasyLineupService``).

Si applica solo a un turno arrivato al primo blocco, non saltato, non omologato e non ancora
calcolato (nessuna ``EffectiveLineup`` del turno): un turno già calcolato (o finito prima di
questa regola) non si tocca, il ricalcolo non riscrive la storia. Rieseguirla non cambia niente:
dopo il primo passaggio nessuno schierato è fuori rosa e i posti vuoti sono coperti (dal primo
blocco rose e formazioni non cambiano più se non con un salvataggio completo), e chi la esegue
rilegge la formazione sotto blocco. Le formazioni automatiche «a zero» (nessuna formazione,
nessuna bozza valida) restano vuote: non sono formazioni con un posto vuoto. Una squadra senza
rosa non si tocca: non c'è niente con cui confrontare la formazione.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from database.enums import (
    FantasyRole,
    FantasyRoundHomologationStatus,
    FantasyTurnStatus,
    LeagueAuditAction,
    LineupAutoResolutionSource,
    LineupSlotKind,
)
from fantasy_lineups.availability import no_vote_reasons, probable_hints
from fantasy_lineups.departures import (
    DEPARTURE_AUDIT_SOURCE,
    lock_margin_minutes,
    team_owner_id,
    turn_has_started,
)
from fantasy_lineups.kickoffs import athlete_kickoffs
from fantasy_lineups.models import EffectiveLineup, LineupPlayer, LineupSubmission
from fantasy_lineups.rules import (
    BENCH_ACTIVE_ROLE_QUOTA_MESSAGE,
    TURN_START_FROM_BENCH,
    TURN_START_FROM_TRIBUNA,
    LineupPlayerRef,
    TurnStartHoleFill,
    bench_active_role_shortfall,
    fill_lineup_holes_at_turn_start,
    fill_starter_holes,
    is_athlete_kickoff_locked,
    join_names,
    restore_bench_active_roles,
    turn_start_role_label,
)
from fantasy_lineups.validators import MAX_LINEUP_LOCK_MARGIN_MINUTES
from fantasy_teams.composition_service import resolve_effective_athlete_roles
from fantasy_teams.models import FantasyRosterSlot
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.rules import STARTED_FIXTURE_STATUSES, ensure_utc
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from observability.context import get_correlation_id
from observability.logging import get_logger
from sports_data.fixtures.models import Fixture
from sports_data.roster.models import Athlete

logger = get_logger(__name__)

#: ``details.source`` dell'evento di audit scritto dalla regola di inizio turno.
TURN_START_AUDIT_SOURCE = "turn_start_autofill"
#: Il job guarda solo i turni la cui finestra è finita da poco: un turno arrivato al primo
#: blocco e mai calcolato oltre questo limite lo sistema comunque il calcolo, quando parte.
TURN_START_SWEEP_HORIZON = timedelta(days=3)
#: Posizioni di appoggio per riordinare senza violare l'unicità
#: ``(submission_id, slot_kind, sort_order)`` durante gli UPDATE (come ``departures``).
_SORT_ORDER_PARKING = 20_000


@dataclass(frozen=True)
class TurnStartTeamChange:
    """Una formazione sistemata all'inizio del turno."""

    fantasy_team_id: UUID
    #: Chi è stato tolto perché non più in rosa.
    removed_athlete_ids: tuple[UUID, ...]
    #: I posti vuoti tra i titolari e come sono stati coperti.
    fills: tuple[TurnStartHoleFill, ...]


@dataclass
class TurnStartResult:
    round_id: UUID
    #: La regola valeva per questo turno (primo blocco raggiunto, non calcolato né omologato).
    due: bool = False
    teams_checked: int = 0
    changes: list[TurnStartTeamChange] = field(default_factory=list)

    @property
    def teams_changed(self) -> int:
        return len(self.changes)


@dataclass(frozen=True)
class TurnStartNotice:
    """Avviso di GET formazione ricavato dall'audit della regola di inizio turno."""

    applied_at: datetime
    messages: tuple[str, ...]
    #: Chi è uscito dalla rosa ed è citato nell'avviso (tolto ora o prima, all'uscita).
    departed_athlete_ids: frozenset[str]


def round_already_scored(session: Session, round_id: UUID) -> bool:
    """Il calcolo del turno è già partito: esiste almeno una formazione effettiva."""
    return (
        session.scalar(
            select(EffectiveLineup.id).where(EffectiveLineup.round_id == round_id).limit(1)
        )
        is not None
    )


def turn_start_due(session: Session, fantasy_round: FantasyRound, *, now: datetime) -> bool:
    """La regola vale per il turno: primo blocco raggiunto, non saltato, omologato o calcolato."""
    if fantasy_round.status == FantasyTurnStatus.SKIPPED:
        return False
    if (
        fantasy_round.homologated_at is not None
        or fantasy_round.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED
    ):
        return False
    margin = lock_margin_minutes(session, fantasy_round.league_id)
    if not turn_has_started(session, fantasy_round, now=ensure_utc(now), margin_minutes=margin):
        return False
    return not round_already_scored(session, fantasy_round.id)


def settle_lineups_at_turn_start(
    session: Session,
    *,
    fantasy_round: FantasyRound,
    now: datetime | None = None,
    team_ids: set[UUID] | None = None,
) -> TurnStartResult:
    """Applica la regola di inizio turno alle formazioni del turno (solo ``team_ids`` se dato).

    Non fa niente se il turno non è ancora al primo blocco, o è saltato, omologato o già
    calcolato. Solo ``flush``: il commit resta al chiamante.
    """
    moment = ensure_utc(now or datetime.now(UTC))
    result = TurnStartResult(round_id=fantasy_round.id)
    # Le sessioni non fanno autoflush: cutoff e partite appena riallineati (o la formazione
    # automatica appena creata) devono arrivare al DB prima delle query.
    session.flush()
    if not turn_start_due(session, fantasy_round, now=moment):
        return result
    result.due = True
    league = session.get(League, fantasy_round.league_id)
    if league is None:
        return result
    query = select(LineupSubmission.id, LineupSubmission.fantasy_team_id).where(
        LineupSubmission.round_id == fantasy_round.id,
        or_(
            LineupSubmission.auto_resolution_source.is_(None),
            LineupSubmission.auto_resolution_source != LineupAutoResolutionSource.ZERO_FALLBACK,
        ),
    )
    if team_ids is not None:
        if not team_ids:
            return result
        query = query.where(LineupSubmission.fantasy_team_id.in_(team_ids))
    rows = session.execute(query.order_by(LineupSubmission.fantasy_team_id)).all()
    for submission_id, team_id in rows:
        result.teams_checked += 1
        change = _settle_submission(
            session,
            league=league,
            fantasy_round=fantasy_round,
            submission_id=submission_id,
            team_id=team_id,
            now=moment,
        )
        if change is not None:
            result.changes.append(change)
    if result.changes:
        session.flush()
        logger.info(
            "fantasy_lineup_turn_start_autofill",
            extra={
                "round_id": str(fantasy_round.id),
                "teams_checked": result.teams_checked,
                "teams_changed": result.teams_changed,
            },
        )
    return result


def settle_started_turns(
    session: Session,
    *,
    now: datetime | None = None,
    horizon: timedelta = TURN_START_SWEEP_HORIZON,
) -> list[TurnStartResult]:
    """Il passaggio del job: i turni arrivati al primo blocco e non ancora calcolati.

    Un turno alla volta, ciascuno nella sua transazione (un errore in una lega non ferma le
    altre). Il commit è qui, come in ``process_live_fantasy_rounds``.
    """
    moment = ensure_utc(now or datetime.now(UTC))
    # Superinsieme del primo blocco (margine massimo di lega): il controllo esatto, con il
    # margine della lega, è in ``turn_start_due``.
    latest_first_lock = moment + timedelta(minutes=MAX_LINEUP_LOCK_MARGIN_MINUTES)
    locked_fixture_rounds = (
        select(FantasyRoundFixture.round_id)
        .join(Fixture, Fixture.id == FantasyRoundFixture.fixture_id)
        .where(
            FantasyRoundFixture.excluded_at.is_(None),
            or_(
                Fixture.kickoff_at <= latest_first_lock,
                Fixture.status_short.in_(tuple(STARTED_FIXTURE_STATUSES)),
                FantasyRoundFixture.lock_latched_at.is_not(None),
            ),
        )
    )
    scored = select(EffectiveLineup.id).where(EffectiveLineup.round_id == FantasyRound.id)
    fielded = select(LineupSubmission.id).where(LineupSubmission.round_id == FantasyRound.id)
    round_ids = list(
        session.scalars(
            select(FantasyRound.id)
            .where(
                FantasyRound.status != FantasyTurnStatus.SKIPPED,
                FantasyRound.homologated_at.is_(None),
                FantasyRound.homologation_status == FantasyRoundHomologationStatus.PROVISIONAL,
                FantasyRound.window_end_at >= moment - horizon,
                or_(
                    FantasyRound.cutoff_at <= latest_first_lock,
                    FantasyRound.id.in_(locked_fixture_rounds),
                ),
                ~scored.exists(),
                fielded.exists(),
            )
            .order_by(FantasyRound.league_id, FantasyRound.number)
        ).all()
    )
    results: list[TurnStartResult] = []
    for round_id in round_ids:
        session.commit()
        try:
            with session.begin_nested():
                fantasy_round = session.get(FantasyRound, round_id)
                if fantasy_round is None:
                    continue
                results.append(
                    settle_lineups_at_turn_start(session, fantasy_round=fantasy_round, now=moment)
                )
        except Exception:  # noqa: BLE001 - una lega con dati rotti non ferma le altre
            logger.exception("fantasy_lineup_turn_start_failed", extra={"round_id": str(round_id)})
    session.commit()
    return results


def turn_start_notices(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    team_id: UUID,
) -> list[TurnStartNotice]:
    """Gli avvisi della regola di inizio turno per la formazione di questa squadra."""
    rows = session.scalars(
        select(LeagueAuditEvent.details)
        .where(
            LeagueAuditEvent.league_id == league_id,
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_SAVED,
            LeagueAuditEvent.details.contains(
                {
                    "source": TURN_START_AUDIT_SOURCE,
                    "roundId": str(round_id),
                    "fantasyTeamId": str(team_id),
                }
            ),
        )
        .order_by(LeagueAuditEvent.created_at.asc())
    ).all()
    notices: list[TurnStartNotice] = []
    for details in rows:
        if not isinstance(details, dict):
            continue
        try:
            applied_at = ensure_utc(datetime.fromisoformat(str(details.get("appliedAt"))))
        except ValueError:
            continue
        departed = {
            str(item.get("athleteId"))
            for item in details.get("removed") or ()
            if isinstance(item, dict) and item.get("athleteId")
        } | {
            str(item.get("leftById"))
            for item in details.get("fills") or ()
            if isinstance(item, dict) and item.get("leftById")
        }
        messages = turn_start_messages(details)
        if messages:
            notices.append(
                TurnStartNotice(
                    applied_at=applied_at,
                    messages=tuple(messages),
                    departed_athlete_ids=frozenset(departed),
                )
            )
    return notices


def turn_start_messages(details: dict) -> list[str]:
    """«All'inizio del turno 5 L. Rossi è entrato al posto di N. Zortea (non più in rosa); …»."""
    number = details.get("roundNumber")
    opening = f"All'inizio del turno {number}" if number is not None else "All'inizio del turno"
    messages: list[str] = []
    for fill in details.get("fills") or ():
        if not isinstance(fill, dict):
            continue
        try:
            role = FantasyRole(fill["role"]) if fill.get("role") else None
        except ValueError:
            role = None
        label = turn_start_role_label(role)
        left = fill.get("leftByName")
        place = (
            f"al posto di {left} (non più in rosa)" if left else "nel posto libero tra i titolari"
        )
        starter = fill.get("starterName") or f"un {label}"
        source = fill.get("source")
        if source == TURN_START_FROM_BENCH:
            refill = fill.get("benchName") or (f"un {label}" if fill.get("benchId") else None)
            tail = f"; dalla tribuna è salito in panchina {refill}." if refill else "."
            messages.append(f"{opening} {starter} è entrato {place}{tail}")
        elif source == TURN_START_FROM_TRIBUNA:
            messages.append(
                f"{opening} {starter} è entrato dalla tribuna {place}: "
                f"in panchina non c'era nessun {label} da far entrare."
            )
        else:
            what = (
                f"il posto di {left} (non più in rosa)"
                if left
                else f"un posto da {label} tra i titolari"
            )
            messages.append(
                f"{opening} {what} è rimasto vuoto: "
                f"in rosa non c'è nessun altro {label} da schierare."
            )
    cited = {
        str(fill.get("leftById"))
        for fill in details.get("fills") or ()
        if isinstance(fill, dict) and fill.get("leftById")
    }
    others = [
        str(item.get("athleteName") or "")
        for item in details.get("removed") or ()
        if isinstance(item, dict) and str(item.get("athleteId")) not in cited
    ]
    others = [name for name in others if name]
    for move in details.get("benchRepair") or ():
        if not isinstance(move, dict):
            continue
        promoted = move.get("promotedName") or "un calciatore della tribuna"
        demoted = move.get("demotedName") or "chi era in più"
        messages.append(
            f"{opening} {promoted} è salito in panchina al posto di {demoted}, che va in "
            f"tribuna: {BENCH_ACTIVE_ROLE_QUOTA_MESSAGE[0].lower()}"
            f"{BENCH_ACTIVE_ROLE_QUOTA_MESSAGE[1:]}."
        )
    if others:
        if len(others) == 1:
            messages.append(
                f"{opening} {others[0]} è stato tolto dalla formazione: non è più nella tua rosa."
            )
        else:
            messages.append(
                f"{opening} {join_names(others)} sono stati tolti dalla formazione: "
                "non sono più nella tua rosa."
            )
    return messages


def _settle_submission(
    session: Session,
    *,
    league: League,
    fantasy_round: FantasyRound,
    submission_id: UUID,
    team_id: UUID,
    now: datetime,
) -> TurnStartTeamChange | None:
    # Prima una lettura senza blocco: quasi sempre non c'è niente da fare. Se c'è, la formazione
    # si rilegge sotto lo stesso blocco del salvataggio e della pulizia all'uscita, così chi
    # arriva secondo trova il lavoro già fatto e non cambia niente.
    for locked in (False, True):
        query = (
            select(LineupSubmission)
            .where(LineupSubmission.id == submission_id)
            .options(selectinload(LineupSubmission.players))
            .execution_options(populate_existing=True)
        )
        if locked:
            query = query.with_for_update(of=LineupSubmission)
        submission = session.scalars(query).one_or_none()
        if submission is None:
            return None
        roster = session.execute(
            select(
                FantasyRosterSlot.athlete_id,
                FantasyRosterSlot.exceeds_role_quota,
            )
            .where(
                FantasyRosterSlot.fantasy_team_id == team_id,
                FantasyRosterSlot.athlete_id.is_not(None),
            )
            .order_by(FantasyRosterSlot.slot_index.asc())
        ).all()
        if not roster:
            return None
        owned = {athlete_id for athlete_id, _ in roster}
        departed = [row for row in submission.players if row.athlete_id not in owned]
        kept = [row for row in submission.players if row.athlete_id in owned]
        starters = [
            (row.sort_order, LineupPlayerRef(athlete_id=row.athlete_id, role=row.role))
            for row in kept
            if row.slot_kind == LineupSlotKind.STARTER
        ]
        has_hole = any(
            ref.athlete_id == ""
            for ref in fill_starter_holes(module=submission.module.value, starters=starters)
        )
        bench = [
            LineupPlayerRef(athlete_id=row.athlete_id, role=row.role)
            for row in sorted(
                (row for row in kept if row.slot_kind == LineupSlotKind.BENCH),
                key=lambda row: row.sort_order,
            )
        ]
        # Nei primi 10 manca un ruolo (es. un portiere salito al posto di un attaccante uscito
        # dalla rosa, Rosario 20/11): anche questo si sistema all'inizio del turno.
        bench_short = bool(
            bench_active_role_shortfall(
                bench,
                unavailable_athlete_ids={athlete_id for athlete_id, excess in roster if excess},
            )
        )
        if not departed and not has_hole and not bench_short:
            return None

    roster_ids = [athlete_id for athlete_id, _ in roster]
    effective_roles = resolve_effective_athlete_roles(
        session,
        league_id=league.id,
        athlete_ids=roster_ids,
        season_year=league.season_year,
        current_round=fantasy_round.number,
    )
    kickoffs = athlete_kickoffs(
        session,
        round_id=fantasy_round.id,
        season_year=league.season_year,
        athlete_ids=roster_ids,
    )
    reasons = no_vote_reasons(
        roster_ids,
        kickoffs,
        probable_hints(session, fantasy_round.id, roster_ids),
    )
    roles = {
        athlete_id: (effective_roles[athlete_id].role if athlete_id in effective_roles else None)
        for athlete_id in roster_ids
    }
    unavailable = {
        *reasons,
        *(athlete_id for athlete_id, excess in roster if excess),
        *(athlete_id for athlete_id, role in roles.items() if role is None),
    }
    fielded = {row.athlete_id for row in kept}
    outside = [
        LineupPlayerRef(athlete_id=athlete_id, role=roles[athlete_id])
        for athlete_id, excess in roster
        if athlete_id not in fielded and not excess and roles[athlete_id] is not None
    ]
    outcome = fill_lineup_holes_at_turn_start(
        module=submission.module.value,
        starters=starters,
        bench=bench,
        outside=outside,
        unavailable_ids=unavailable,
    )
    # La quota per ruolo dei primi 10: chi è uscito ha fatto scalare la panchina, o un
    # panchinaro entrato tra i titolari non aveva nessuno dello stesso ruolo in tribuna. Sale il
    # primo della tribuna con il ruolo che manca; chi ha la partita già iniziata non si sposta
    # (in tribuna lo si può scavalcare: lì non entra comunque).
    margin = lock_margin_minutes(session, league.id)
    locked = {
        athlete_id
        for athlete_id, ref in kickoffs.items()
        if is_athlete_kickoff_locked(
            now=now,
            kickoff_at=ref.kickoff_at,
            status_short=ref.status_short,
            lock_latched=ref.lock_latched,
            margin_minutes=margin,
        )
    }
    repair = restore_bench_active_roles(
        outcome.bench,
        locked_athlete_ids=locked,
        unavailable_athlete_ids={
            *(athlete_id for athlete_id, excess in roster if excess),
            *(athlete_id for athlete_id, role in roles.items() if role is None),
        },
        # Come la validazione: chi non prende il voto non alza la quota (una formazione
        # salvata valida non si tocca) e non sale nei primi 10.
        unfieldable_athlete_ids=set(reasons),
        overtake_locked_in_tribuna=True,
    )
    if not departed and not outcome.changed and not repair.changed:
        # Un posto vuoto (o un ruolo nei primi 10) che nessuno può coprire: niente da scrivere.
        return None

    # Prima di scrivere: le righe di chi esce vengono cancellate.
    departed_ids = tuple(row.athlete_id for row in departed)
    removed_starters = {
        row.sort_order: row.athlete_id
        for row in departed
        if row.slot_kind == LineupSlotKind.STARTER
    }
    removed = [
        {
            "athleteId": str(row.athlete_id),
            "slotKind": row.slot_kind.value,
            "sortOrder": row.sort_order,
        }
        for row in sorted(
            departed, key=lambda row: (row.slot_kind != LineupSlotKind.STARTER, row.sort_order)
        )
    ]
    module, revision = submission.module.value, submission.revision
    _write_rows(session, submission, starters=outcome.starters, bench=repair.bench)

    involved = {
        *departed_ids,
        *(item.starter_athlete_id for item in outcome.fills if item.starter_athlete_id),
        *(item.bench_athlete_id for item in outcome.fills if item.bench_athlete_id),
        *(athlete_id for move in repair.moves for athlete_id in move),
    }
    left_by = _left_by(
        session,
        league_id=league.id,
        round_id=fantasy_round.id,
        team_id=team_id,
        positions={item.starter_position for item in outcome.fills},
        removed_now=removed_starters,
        owned=owned,
    )
    involved |= {athlete_id for athlete_id, _ in left_by.values()}
    names = _athlete_names(session, involved)
    for item in removed:
        item["athleteName"] = names.get(UUID(item["athleteId"]), "")
    fills = []
    for item in outcome.fills:
        left = left_by.get(item.starter_position)
        fills.append(
            {
                "role": item.role.value if item.role is not None else None,
                "starterSortOrder": item.starter_position,
                "leftById": str(left[0]) if left is not None else None,
                "leftByName": (names.get(left[0]) or left[1]) if left is not None else None,
                "source": item.source,
                "starterId": str(item.starter_athlete_id) if item.starter_athlete_id else None,
                "starterName": (
                    names.get(item.starter_athlete_id, "") if item.starter_athlete_id else None
                ),
                "fromBenchSortOrder": item.from_bench_position,
                "benchId": str(item.bench_athlete_id) if item.bench_athlete_id else None,
                "benchName": (
                    names.get(item.bench_athlete_id, "") if item.bench_athlete_id else None
                ),
                "benchSortOrder": item.bench_position,
                "benchFromSortOrder": item.bench_from_position,
            }
        )
    session.add(
        LeagueAuditEvent(
            league_id=league.id,
            # Regola di sistema, non una scelta: come la pulizia all'uscita senza autore, l'evento
            # va al proprietario della squadra; ``source`` dice che l'ha fatto il sistema.
            actor_id=team_owner_id(session, team_id),
            action=LeagueAuditAction.FANTASY_LINEUP_SAVED,
            correlation_id=get_correlation_id(),
            details={
                "source": TURN_START_AUDIT_SOURCE,
                "roundId": str(fantasy_round.id),
                "roundNumber": fantasy_round.number,
                "fantasyTeamId": str(team_id),
                "appliedAt": now.isoformat(),
                "module": module,
                "revision": revision,
                "tacticalMoveConsumed": False,
                "removed": removed,
                "fills": fills,
                # Chi è salito dalla tribuna nei primi 10 per la quota per ruolo, e chi è sceso.
                "benchRepair": [
                    {
                        "promotedId": str(promoted),
                        "promotedName": names.get(promoted, ""),  # type: ignore[call-overload]
                        "demotedId": str(demoted),
                        "demotedName": names.get(demoted, ""),  # type: ignore[call-overload]
                    }
                    for promoted, demoted in repair.moves
                ],
            },
        )
    )
    session.flush()
    return TurnStartTeamChange(
        fantasy_team_id=team_id,
        removed_athlete_ids=departed_ids,
        fills=outcome.fills,
    )


def _write_rows(
    session: Session,
    submission: LineupSubmission,
    *,
    starters: tuple[tuple[int, LineupPlayerRef], ...],
    bench: tuple[LineupPlayerRef, ...],
) -> None:
    """Porta le righe ``LineupPlayer`` alla formazione data (titolari per posto, panchina)."""
    targets: dict[object, tuple[LineupSlotKind, int, FantasyRole | None]] = {}
    for position, ref in starters:
        targets[ref.athlete_id] = (LineupSlotKind.STARTER, position, ref.role)
    for index, ref in enumerate(bench):
        targets[ref.athlete_id] = (LineupSlotKind.BENCH, index, ref.role)
    # delete-orphan: chi non è più in rosa esce davvero, prima di riordinare (unicità).
    for row in list(submission.players):
        if row.athlete_id not in targets:
            submission.players.remove(row)
    session.flush()
    moved = [
        row
        for row in submission.players
        if (row.slot_kind, row.sort_order) != targets[row.athlete_id][:2]
    ]
    if moved:
        for offset, row in enumerate(moved):
            row.sort_order = _SORT_ORDER_PARKING + offset
        session.flush()
        for row in moved:
            row.slot_kind, row.sort_order = targets[row.athlete_id][:2]
        session.flush()
    present = {row.athlete_id for row in submission.players}
    for athlete_id, (slot_kind, sort_order, role) in targets.items():
        if athlete_id in present or role is None:
            continue
        # In rosa ma non nella formazione: entra con il ruolo di questo turno.
        submission.players.append(
            LineupPlayer(
                athlete_id=athlete_id,
                slot_kind=slot_kind,
                role=role,
                sort_order=sort_order,
            )
        )
    session.flush()
    session.expire(submission, ["players"])


def _left_by(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    team_id: UUID,
    positions: set[int],
    removed_now: dict[int, UUID],
    owned: set[UUID],
) -> dict[int, tuple[UUID, str]]:
    """Per ogni posto vuoto, chi lo occupava prima di uscire dalla rosa (se si sa)."""
    found: dict[int, tuple[UUID, str]] = {
        position: (athlete_id, "")
        for position, athlete_id in removed_now.items()
        if position in positions
    }
    missing = positions - set(found)
    if not missing:
        return found
    # Tolto prima, all'uscita dalla rosa: l'audit della pulizia dice da quale posto.
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
                    "lineupSlotKind": LineupSlotKind.STARTER.value,
                }
            ),
        )
        .order_by(LeagueAuditEvent.created_at.desc())
    ).all()
    for details in rows:
        if not isinstance(details, dict):
            continue
        position = details.get("lineupSortOrder")
        if position not in missing:
            continue
        try:
            athlete_id = UUID(str(details.get("athleteId")))
        except ValueError:
            continue
        if athlete_id in owned:
            continue
        found[position] = (athlete_id, str(details.get("athleteName") or ""))
        missing.discard(position)
    return found


def _athlete_names(session: Session, athlete_ids: set[object]) -> dict[UUID, str]:
    ids = [item for item in athlete_ids if isinstance(item, UUID)]
    if not ids:
        return {}
    return {
        athlete_id: name
        for athlete_id, name in session.execute(
            select(Athlete.id, Athlete.canonical_name).where(Athlete.id.in_(ids))
        ).all()
    }


__all__ = [
    "TURN_START_AUDIT_SOURCE",
    "TURN_START_SWEEP_HORIZON",
    "TurnStartNotice",
    "TurnStartResult",
    "TurnStartTeamChange",
    "round_already_scored",
    "settle_lineups_at_turn_start",
    "settle_started_turns",
    "turn_start_due",
    "turn_start_messages",
    "turn_start_notices",
]
