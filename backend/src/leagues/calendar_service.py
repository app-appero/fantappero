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
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.schedule import (
    assert_schedule_invariants,
    generate_single_round_robin,
    participant_fingerprint,
)
from leagues.schemas import (
    LeagueCalendarMatchupResponse,
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
        schedule = generate_single_round_robin(membership_ids)
        assert_schedule_invariants(schedule, membership_ids)
        fingerprint = participant_fingerprint(membership_ids)
        now = datetime.now(UTC)

        calendar = self._session.scalars(
            select(LeagueCalendar)
            .where(LeagueCalendar.league_id == league.id)
            .with_for_update()
        ).first()
        if calendar is None:
            calendar = LeagueCalendar(league_id=league.id)
            self._session.add(calendar)
        else:
            self._session.execute(
                delete(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
            )
            self._session.expire(calendar, ["slots"])

        calendar.status = LeagueCalendarStatus.DRAFT
        calendar.format = LeagueCalendarFormat.SINGLE_ROUND_ROBIN
        calendar.algorithm_version = schedule.algorithm_version
        calendar.participant_fingerprint = fingerprint
        calendar.participant_count = schedule.participant_count
        calendar.round_count = schedule.round_count
        calendar.matchup_count = schedule.matchup_count
        calendar.bye_count = schedule.bye_count
        calendar.generated_at = now
        calendar.confirmed_at = None
        self._session.flush()
        for slot in schedule.slots:
            calendar.slots.append(
                LeagueCalendarSlot(
                    round_number=slot.round_number,
                    slot_index=slot.slot_index,
                    is_bye=slot.is_bye,
                    home_membership_id=slot.home_membership_id,
                    away_membership_id=slot.away_membership_id,
                )
            )

        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_CALENDAR_GENERATED,
                correlation_id=get_correlation_id(),
                details={
                    "algorithmVersion": schedule.algorithm_version,
                    "format": LeagueCalendarFormat.SINGLE_ROUND_ROBIN.value,
                    "participantCount": schedule.participant_count,
                    "roundCount": schedule.round_count,
                    "matchupCount": schedule.matchup_count,
                    "byeCount": schedule.bye_count,
                },
            )
        )
        self._session.commit()
        get_metrics().incr("league_calendar_generated_total", labels={"result": "success"})
        logger.info(
            "league_calendar_generated",
            extra={
                "result": "success",
                "participant_count": schedule.participant_count,
                "round_count": schedule.round_count,
                "matchup_count": schedule.matchup_count,
            },
        )
        return self._to_response(self._load_calendar(league.id))

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
            rounds.append(
                LeagueCalendarRoundResponse(roundNumber=round_number, matchups=matchups)
            )

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
