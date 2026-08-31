"""League H2H calendar generation and confirmation (EP03-06)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from authorization.context import LeagueAccess
from database.enums import (
    LeagueAuditAction,
    LeagueCalendarFormat,
    LeagueCalendarStatus,
)
from fantasy_turns.models import FantasyRound
from fantasy_turns.rules import DEFAULT_LEAGUE_TZ
from leagues.calendar_planning import (
    CalendarPlan,
    WindowCandidate,
    assert_plan_invariants,
    plan_calendar,
    windows_fingerprint,
)
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import (
    LeagueCalendar,
    LeagueCalendarRoundWindow,
    LeagueCalendarSlot,
)
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.schedule import participant_fingerprint
from leagues.schemas import (
    CalendarPlannedRoundResponse,
    CalendarWindowResponse,
    LeagueCalendarMatchupResponse,
    LeagueCalendarPlanResponse,
    LeagueCalendarResponse,
    LeagueCalendarRoundResponse,
    LeagueCalendarSummaryResponse,
)
from leagues.validators import (
    validate_calendar_generation_state,
    validate_calendar_participant_alignment,
)
from observability.context import get_correlation_id
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)


def _window_payload(window: WindowCandidate) -> CalendarWindowResponse:
    return CalendarWindowResponse(
        startAt=window.start_at,
        endAt=window.end_at,
        kind=window.kind.value,
        timezone=window.timezone,
        fixtureCount=window.fixture_count,
        minRequired=window.min_required,
        eligible=window.eligible,
        reason=window.reason,
    )


class LeagueCalendarService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_admin_calendar(self, league_access: LeagueAccess) -> LeagueCalendarResponse | None:
        calendar = self._load_calendar(league_access.league.id)
        if calendar is None:
            return None
        if not self._fingerprint_matches(calendar, league_access.league.id):
            return None
        return self._to_response(calendar)

    def get_public_calendar(self, league_access: LeagueAccess) -> LeagueCalendarResponse | None:
        calendar = self._load_calendar(league_access.league.id)
        if calendar is None or calendar.status != LeagueCalendarStatus.CONFIRMED:
            return None
        if not self._fingerprint_matches(calendar, league_access.league.id):
            return None
        return self._to_response(calendar)

    def generate(self, league_access: LeagueAccess) -> LeagueCalendarResponse:
        league = self._lock_league(league_access.league.id)
        try:
            validate_calendar_generation_state(league.state)
        except ValidationAuthError:
            get_metrics().incr("league_calendar_generated_total", labels={"result": "locked"})
            raise

        memberships = self._load_memberships(league.id, for_update=True)
        rules = self._load_rules(league.id)
        try:
            validate_calendar_participant_alignment(
                membership_count=len(memberships),
                participant_count=rules.participant_count if rules is not None else None,
            )
        except ValidationAuthError as exc:
            get_metrics().incr(
                "league_calendar_generated_total",
                labels={"result": exc.code},
            )
            raise

        membership_ids = [row.id for row in memberships]
        # Un solo motore temporale: le giornate H2H sono i Turni Europei
        # della lega, non un calcolo parallelo. Quanti turni ci sono lo decide
        # il motore dei turni; il numero di partecipanti decide solo *come*
        # ruotano gli accoppiamenti, non quante giornate dura la stagione.
        european_rounds = self._european_rounds(league)
        if not european_rounds:
            get_metrics().incr(
                "league_calendar_generated_total",
                labels={"result": "no_european_turns"},
            )
            raise ValidationAuthError(
                "Non ci sono ancora Turni Europei validi per questa lega: il "
                "calendario dei fantallenatori si genera da quelli.",
                code="european_turns_missing",
            )

        windows = self.build_windows(league)
        plan = plan_calendar(membership_ids, windows)
        if plan.round_count == 0:
            # Ci sono turni, ma tutti iniziati prima che la lega esistesse:
            # nessuna giornata giocabile. Meglio dirlo che scrivere un
            # calendario vuoto (che violerebbe anche il vincolo su round_count).
            get_metrics().incr(
                "league_calendar_generated_total",
                labels={"result": "no_playable_turns"},
            )
            raise ValidationAuthError(
                "Tutti i Turni Europei di questa lega iniziano prima della sua "
                "creazione: non c'è ancora una giornata da disputare.",
                code="european_turns_before_creation",
            )
        assert_plan_invariants(plan, membership_ids)
        slots = plan.slots
        round_count = plan.round_count
        matchup_count = plan.matchup_count
        bye_count = plan.bye_count
        algorithm_version = plan.algorithm_version

        # Numerazione presa **dai Turni Europei**, non ricalcolata: la giornata
        # N dei fantallenatori è il Turno Europeo N. Agganciata sulla finestra
        # temporale, l'unica identità stabile fra le due tabelle.
        number_by_window = {
            (row.window_start_at, row.window_end_at): row.number for row in european_rounds
        }
        local_to_absolute: dict[int, int] = {
            planned.round_number: number_by_window[
                (planned.window_start_at, planned.window_end_at)
            ]
            for planned in plan.rounds
        }

        fingerprint = participant_fingerprint(membership_ids)
        now = datetime.now(UTC)

        calendar = self._session.scalars(
            select(LeagueCalendar).where(LeagueCalendar.league_id == league.id).with_for_update()
        ).first()
        if calendar is None:
            calendar = LeagueCalendar(league_id=league.id)
            self._session.add(calendar)
        else:
            self._session.execute(
                delete(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
            )
            self._session.execute(
                delete(LeagueCalendarRoundWindow).where(
                    LeagueCalendarRoundWindow.calendar_id == calendar.id
                )
            )
            self._session.expire(calendar, ["slots", "round_windows"])

        calendar.status = LeagueCalendarStatus.DRAFT
        calendar.format = LeagueCalendarFormat.SINGLE_ROUND_ROBIN
        calendar.algorithm_version = algorithm_version
        calendar.participant_fingerprint = fingerprint
        calendar.participant_count = len(membership_ids)
        calendar.round_count = round_count
        calendar.matchup_count = matchup_count
        calendar.bye_count = bye_count
        calendar.cycle_length = plan.cycle_length
        calendar.cycle_count = plan.cycle_count
        calendar.windows_fingerprint = plan.windows_fingerprint
        calendar.generated_at = now
        calendar.confirmed_at = None
        self._session.flush()
        for slot in slots:
            calendar.slots.append(
                LeagueCalendarSlot(
                    round_number=local_to_absolute.get(slot.round_number, slot.round_number),
                    slot_index=slot.slot_index,
                    is_bye=slot.is_bye,
                    home_membership_id=slot.home_membership_id,
                    away_membership_id=slot.away_membership_id,
                )
            )
        for planned in plan.rounds:
            calendar.round_windows.append(
                LeagueCalendarRoundWindow(
                    round_number=local_to_absolute[planned.round_number],
                    cycle_number=planned.cycle_number,
                    cycle_round_number=planned.cycle_round_number,
                    window_start_at=planned.window_start_at,
                    window_end_at=planned.window_end_at,
                    window_kind=planned.window_kind.value,
                )
            )

        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_CALENDAR_GENERATED,
                correlation_id=get_correlation_id(),
                details={
                    "algorithmVersion": algorithm_version,
                    "format": LeagueCalendarFormat.SINGLE_ROUND_ROBIN.value,
                    "participantCount": len(membership_ids),
                    "roundCount": round_count,
                    "matchupCount": matchup_count,
                    "byeCount": bye_count,
                    "cycleCount": plan.cycle_count,
                    "cycleLength": plan.cycle_length,
                    "eligibleWindows": plan.eligible_window_count,
                    "discardedWindows": len(plan.windows_discarded),
                },
            )
        )
        self._session.commit()
        get_metrics().incr(
            "league_calendar_generated_total",
            labels={"result": "success"},
        )
        logger.info(
            "league_calendar_generated",
            extra={
                "result": "success",
                "participant_count": len(membership_ids),
                "round_count": round_count,
                "matchup_count": matchup_count,
                "cycle_count": plan.cycle_count,
                "eligible_windows": plan.eligible_window_count,
            },
        )
        return self._to_response(self._load_calendar(league.id))

    def build_windows(self, league: League) -> tuple[WindowCandidate, ...]:
        """I Turni Europei della lega, letti così come sono.

        **Un solo motore temporale**: le giornate dei fantallenatori non sono
        ricalcolate da capo dalle fixture, sono i `FantasyRound` già validati
        dal motore di copertura (`fantasy_turns.coverage`). Prima esistevano
        due calcoli paralleli e bastava una rinumerazione dei turni per
        sfasarli: il calendario H2H conservava numeri ormai inesistenti.

        Restano escluse solo le finestre iniziate prima della creazione della
        lega: non possono avere scontri. L'interfaccia le mostra comunque come
        segnaposto "lega creata dopo questo turno", così la numerazione resta
        allineata 1:1 con i Turni Europei.
        """
        rounds = self._european_rounds(league)
        return tuple(
            WindowCandidate(
                start_at=row.window_start_at,
                end_at=row.window_end_at,
                kind=row.kind,
                timezone=str(DEFAULT_LEAGUE_TZ),
                fixture_count=0,
                min_required=0,
                eligible=row.window_start_at >= league.created_at,
                reason=(
                    None
                    if row.window_start_at >= league.created_at
                    else "Lega creata dopo questo turno."
                ),
            )
            for row in rounds
        )

    def _european_rounds(self, league: League) -> list[FantasyRound]:
        """I turni validi della lega, in ordine cronologico di numero."""
        return list(
            self._session.scalars(
                select(FantasyRound)
                .where(FantasyRound.league_id == league.id)
                .order_by(FantasyRound.number.asc())
            ).all()
        )

    def realign_round_numbers(self, league: League) -> int:
        """Riporta le giornate H2H sui numeri attuali dei Turni Europei.

        Il numero di giornata era una **copia** presa al momento della
        generazione: rinumerare i turni (o rimuoverne di non validi) lo
        rendeva obsoleto, ed è la causa delle giornate "5, 7, 8, 10…" viste
        accanto a Turni Europei "1, 2, 3…". L'aggancio avviene sulla finestra
        temporale, che è l'unica identità stabile fra le due tabelle.
        """
        calendar = self._load_calendar(league.id)
        if calendar is None:
            return 0
        by_window = {
            (row.window_start_at, row.window_end_at): row.number
            for row in self._european_rounds(league)
        }
        # Giornate la cui finestra non è più un Turno Europeo valido: il turno
        # non esiste, quindi non deve esistere nemmeno la giornata. Si
        # eliminano solo se non hanno prodotto risultati — un risultato già
        # calcolato non si butta via per una rinumerazione.
        obsolete = {
            window.round_number
            for window in calendar.round_windows
            if (window.window_start_at, window.window_end_at) not in by_window
        }
        protected = {
            slot.round_number
            for slot in calendar.slots
            if slot.round_number in obsolete and slot.result_computed_at is not None
        }
        droppable = obsolete - protected
        if droppable:
            for window in list(calendar.round_windows):
                if window.round_number in droppable:
                    calendar.round_windows.remove(window)
            for slot in list(calendar.slots):
                if slot.round_number in droppable:
                    calendar.slots.remove(slot)
            self._session.flush()

        # Mappa completa vecchio → nuovo, identità inclusa: una giornata che
        # non si sposta occupa comunque un numero che un'altra potrebbe
        # rivendicare, quindi va spostata anch'essa nella passata temporanea.
        remap: dict[int, int] = {}
        changed = 0
        for window in calendar.round_windows:
            target = by_window.get((window.window_start_at, window.window_end_at))
            if target is None:
                remap[window.round_number] = window.round_number
                continue
            remap[window.round_number] = target
            if target != window.round_number:
                changed += 1
        if not changed and not droppable:
            return 0
        if len(set(remap.values())) != len(remap):
            # Due giornate finirebbero sullo stesso turno: il calendario è
            # incoerente oltre quello che una rinumerazione può sistemare,
            # va rigenerato.
            logger.warning(
                "league_calendar_realign_conflict",
                extra={"league_id": str(league.id)},
            )
            return 0

        # Due passate: (calendar_id, round_number) è unico, quindi i numeri di
        # arrivo collidono con quelli ancora da spostare.
        offset = 1_000_000
        for window in calendar.round_windows:
            window.round_number += offset
        for slot in calendar.slots:
            slot.round_number += offset
        self._session.flush()
        for window in calendar.round_windows:
            window.round_number = remap[window.round_number - offset]
        for slot in calendar.slots:
            original = slot.round_number - offset
            slot.round_number = remap.get(original, original)
        calendar.round_count = len({w.round_number for w in calendar.round_windows})
        calendar.matchup_count = sum(1 for slot in calendar.slots if not slot.is_bye)
        calendar.bye_count = sum(1 for slot in calendar.slots if slot.is_bye)
        calendar.windows_fingerprint = windows_fingerprint(self.build_windows(league))
        self._session.flush()
        return changed

    def plan_preview(self, league_access: LeagueAccess) -> CalendarPlan:
        """Diagnostica amministrativa: cosa entra, cosa avanza e perché."""
        league = league_access.league
        memberships = self._load_memberships(league.id)
        return plan_calendar([row.id for row in memberships], self.build_windows(league))

    def plan_preview_response(self, league_access: LeagueAccess) -> LeagueCalendarPlanResponse:
        plan = self.plan_preview(league_access)
        stale = self.is_stale(league_access.league.id)
        if plan.cycle_length == 0:
            summary = (
                "Partecipanti insufficienti: servono almeno due iscritti per "
                "costruire un calendario."
            )
        elif not plan.is_generatable:
            summary = (
                f"Finestre eleggibili insufficienti: ne servono almeno "
                f"{plan.cycle_length} per un ciclo completo, ne risultano "
                f"{plan.eligible_window_count}."
            )
        elif stale:
            summary = (
                "Il calendario provider è cambiato dopo la generazione: "
                "rigenera per riallineare le giornate alle finestre."
            )
        else:
            summary = (
                f"{plan.cycle_count} cicli completi da {plan.cycle_length} giornate "
                f"su {plan.eligible_window_count} finestre eleggibili."
            )
        return LeagueCalendarPlanResponse(
            algorithmVersion=plan.algorithm_version,
            participantCount=plan.participant_count,
            cycleLength=plan.cycle_length,
            cycleCount=plan.cycle_count,
            roundCount=plan.round_count,
            matchupCount=plan.matchup_count,
            byeCount=plan.bye_count,
            eligibleWindowCount=plan.eligible_window_count,
            windowsFingerprint=plan.windows_fingerprint,
            generatable=plan.is_generatable,
            stale=stale,
            rounds=[
                CalendarPlannedRoundResponse(
                    roundNumber=item.round_number,
                    cycleNumber=item.cycle_number,
                    cycleRoundNumber=item.cycle_round_number,
                    windowStartAt=item.window_start_at,
                    windowEndAt=item.window_end_at,
                    windowKind=item.window_kind.value,
                )
                for item in plan.rounds
            ],
            windowsUsed=[_window_payload(item) for item in plan.windows_used],
            windowsDiscarded=[_window_payload(item) for item in plan.windows_discarded],
            summary=summary,
        )

    def is_stale(self, league_id: UUID) -> bool:
        """True se le finestre eleggibili sono cambiate dopo la generazione."""
        calendar = self._load_calendar(league_id)
        if calendar is None or calendar.windows_fingerprint is None:
            return False
        league = self._session.get(League, league_id)
        if league is None:
            return False
        return calendar.windows_fingerprint != windows_fingerprint(self.build_windows(league))

    def confirm(self, league_access: LeagueAccess) -> LeagueCalendarResponse:
        league = self._lock_league(league_access.league.id)
        try:
            validate_calendar_generation_state(league.state)
        except ValidationAuthError:
            get_metrics().incr("league_calendar_confirmed_total", labels={"result": "locked"})
            raise

        calendar = self._session.scalars(
            select(LeagueCalendar)
            .where(LeagueCalendar.league_id == league.id)
            .options(
                selectinload(LeagueCalendar.slots)
                .selectinload(LeagueCalendarSlot.home_membership)
                .selectinload(LeagueMembership.user),
                selectinload(LeagueCalendar.slots)
                .selectinload(LeagueCalendarSlot.away_membership)
                .selectinload(LeagueMembership.user),
            )
            .with_for_update()
        ).first()
        if calendar is None:
            get_metrics().incr("league_calendar_confirmed_total", labels={"result": "missing"})
            raise ValidationAuthError(
                "Genera prima un'anteprima del calendario.",
                code="calendar_not_found",
            )

        memberships = self._load_memberships(league.id, for_update=True)
        membership_ids = [row.id for row in memberships]
        fingerprint = participant_fingerprint(membership_ids)
        if calendar.participant_fingerprint != fingerprint:
            get_metrics().incr("league_calendar_confirmed_total", labels={"result": "stale"})
            raise ValidationAuthError(
                "I partecipanti sono cambiati: rigenera il calendario.",
                code="calendar_stale",
            )

        if calendar.status == LeagueCalendarStatus.CONFIRMED:
            get_metrics().incr("league_calendar_confirmed_total", labels={"result": "noop"})
            return self._to_response(calendar)

        calendar.status = LeagueCalendarStatus.CONFIRMED
        calendar.confirmed_at = datetime.now(UTC)
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_CALENDAR_CONFIRMED,
                correlation_id=get_correlation_id(),
                details={
                    "roundCount": calendar.round_count,
                    "matchupCount": calendar.matchup_count,
                    "byeCount": calendar.bye_count,
                },
            )
        )
        self._session.commit()
        get_metrics().incr("league_calendar_confirmed_total", labels={"result": "success"})
        logger.info(
            "league_calendar_confirmed",
            extra={
                "result": "success",
                "round_count": calendar.round_count,
                "matchup_count": calendar.matchup_count,
            },
        )
        return self._to_response(self._load_calendar(league.id))

    def is_configured(self, league_id: UUID) -> bool:
        calendar = self._load_calendar(league_id)
        if calendar is None or calendar.status != LeagueCalendarStatus.CONFIRMED:
            return False
        return self._fingerprint_matches(calendar, league_id)

    def _fingerprint_matches(self, calendar: LeagueCalendar, league_id: UUID) -> bool:
        memberships = self._load_memberships(league_id)
        return calendar.participant_fingerprint == participant_fingerprint(
            [row.id for row in memberships]
        )

    def _lock_league(self, league_id: UUID) -> League:
        league = self._session.scalars(
            select(League).where(League.id == league_id).with_for_update()
        ).first()
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code="league_not_found")
        return league

    def _load_rules(self, league_id: UUID) -> LeagueRules | None:
        return self._session.scalars(
            select(LeagueRules).where(LeagueRules.league_id == league_id)
        ).first()

    def _load_memberships(
        self,
        league_id: UUID,
        *,
        for_update: bool = False,
    ) -> list[LeagueMembership]:
        statement = (
            select(LeagueMembership)
            .where(LeagueMembership.league_id == league_id)
            .options(selectinload(LeagueMembership.user).selectinload(User.profile))
            .order_by(LeagueMembership.created_at.asc(), LeagueMembership.id.asc())
        )
        if for_update:
            statement = statement.with_for_update()
        return list(self._session.scalars(statement).all())

    def _load_calendar(self, league_id: UUID) -> LeagueCalendar | None:
        return self._session.scalars(
            select(LeagueCalendar)
            .where(LeagueCalendar.league_id == league_id)
            .options(
                selectinload(LeagueCalendar.slots)
                .selectinload(LeagueCalendarSlot.home_membership)
                .selectinload(LeagueMembership.user),
                selectinload(LeagueCalendar.slots)
                .selectinload(LeagueCalendarSlot.away_membership)
                .selectinload(LeagueMembership.user),
            )
        ).first()

    def _to_response(self, calendar: LeagueCalendar | None) -> LeagueCalendarResponse:
        if calendar is None:
            raise ValidationAuthError("Calendario non trovato.", code="calendar_not_found")
        rounds_map: dict[int, list[LeagueCalendarSlot]] = defaultdict(list)
        for slot in calendar.slots:
            rounds_map[slot.round_number].append(slot)

        rounds: list[LeagueCalendarRoundResponse] = []
        for round_number in sorted(rounds_map):
            matchups: list[LeagueCalendarMatchupResponse] = []
            for slot in sorted(rounds_map[round_number], key=lambda row: row.slot_index):
                home = slot.home_membership
                away = slot.away_membership
                matchups.append(
                    LeagueCalendarMatchupResponse(
                        slotIndex=slot.slot_index,
                        isBye=slot.is_bye,
                        homeUserId=str(home.user_id),
                        homeDisplayName=home.user.display_name,
                        awayUserId=None if away is None else str(away.user_id),
                        awayDisplayName=None if away is None else away.user.display_name,
                    )
                )
            rounds.append(LeagueCalendarRoundResponse(roundNumber=round_number, matchups=matchups))

        return LeagueCalendarResponse(
            id=str(calendar.id),
            leagueId=str(calendar.league_id),
            status=calendar.status.value,
            format=calendar.format.value,
            algorithmVersion=calendar.algorithm_version,
            participantCount=calendar.participant_count,
            roundCount=calendar.round_count,
            matchupCount=calendar.matchup_count,
            byeCount=calendar.bye_count,
            generatedAt=calendar.generated_at,
            confirmedAt=calendar.confirmed_at,
            rounds=rounds,
            summary=LeagueCalendarSummaryResponse(
                message=(
                    "Anteprima calendario: conferma per associarlo alla lega."
                    if calendar.status == LeagueCalendarStatus.DRAFT
                    else "Calendario confermato e consultabile dai partecipanti."
                ),
            ),
        )


def league_has_confirmed_calendar(session: Session, league_id: UUID) -> bool:
    """Shared helper used by lifecycle blockers without circular imports."""
    return LeagueCalendarService(session).is_configured(league_id)
