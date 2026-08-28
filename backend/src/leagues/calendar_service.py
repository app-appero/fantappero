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
from fantasy_turns.rules import STANDARD_MIN_FIXTURES
from fantasy_turns.service import load_league_candidate_fixtures
from leagues.calendar_planning import (
    CalendarPlan,
    WindowCandidate,
    assert_plan_invariants,
    build_window_candidates,
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
from leagues.schedule import (
    assert_schedule_invariants,
    generate_single_round_robin,
    participant_fingerprint,
)
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
        # EP13-P03: il calendario segue le finestre europee realmente
        # utilizzabili. Se non ce n'è abbastanza per un ciclo completo si
        # ricade sul girone singolo non ancorato, dichiarandolo apertamente.
        windows = self.build_windows(league)
        plan = plan_calendar(membership_ids, windows)
        anchored = plan.is_generatable
        if anchored:
            assert_plan_invariants(plan, membership_ids)
            slots = plan.slots
            round_count = plan.round_count
            matchup_count = plan.matchup_count
            bye_count = plan.bye_count
            algorithm_version = plan.algorithm_version
        else:
            schedule = generate_single_round_robin(membership_ids)
            assert_schedule_invariants(schedule, membership_ids)
            slots = schedule.slots
            round_count = schedule.round_count
            matchup_count = schedule.matchup_count
            bye_count = schedule.bye_count
            algorithm_version = schedule.algorithm_version

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
        calendar.cycle_length = plan.cycle_length if anchored else None
        calendar.cycle_count = plan.cycle_count if anchored else None
        calendar.windows_fingerprint = plan.windows_fingerprint if anchored else None
        calendar.generated_at = now
        calendar.confirmed_at = None
        self._session.flush()
        for slot in slots:
            calendar.slots.append(
                LeagueCalendarSlot(
                    round_number=slot.round_number,
                    slot_index=slot.slot_index,
                    is_bye=slot.is_bye,
                    home_membership_id=slot.home_membership_id,
                    away_membership_id=slot.away_membership_id,
                )
            )
        if anchored:
            for planned in plan.rounds:
                calendar.round_windows.append(
                    LeagueCalendarRoundWindow(
                        round_number=planned.round_number,
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
                    "anchoredToWindows": anchored,
                    "cycleCount": plan.cycle_count if anchored else None,
                    "cycleLength": plan.cycle_length if anchored else None,
                    "eligibleWindows": plan.eligible_window_count,
                    "discardedWindows": len(plan.windows_discarded),
                },
            )
        )
        self._session.commit()
        get_metrics().incr(
            "league_calendar_generated_total",
            labels={"result": "success", "anchored": str(anchored).lower()},
        )
        logger.info(
            "league_calendar_generated",
            extra={
                "result": "success",
                "participant_count": len(membership_ids),
                "round_count": round_count,
                "matchup_count": matchup_count,
                "anchored_to_windows": anchored,
                "cycle_count": plan.cycle_count if anchored else None,
                "eligible_windows": plan.eligible_window_count,
            },
        )
        return self._to_response(self._load_calendar(league.id))

    def build_windows(self, league: League) -> tuple[WindowCandidate, ...]:
        """Finestre europee della stagione con verdetto di eleggibilità."""
        rules = self._load_rules(league.id)
        min_fixtures = rules.min_fixtures_per_round if rules is not None else STANDARD_MIN_FIXTURES
        fixtures = load_league_candidate_fixtures(self._session, league)
        return build_window_candidates(fixtures, min_fixtures=min_fixtures)

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
