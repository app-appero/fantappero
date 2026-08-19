"""European fantasy turn generation and lifecycle (EP06-01)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from authorization.context import LeagueAccess
from database.enums import (
    FantasyRoundFixtureReason,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueAuditAction,
    LeagueMemberRole,
    LeagueState,
)
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.rules import (
    EligibleFixtureRef,
    apply_cutoff_recalculation,
    assert_modification_allowed,
    compute_cutoff,
    derive_effective_status,
    ensure_utc,
    evaluate_threshold,
    is_modification_allowed,
    kickoff_counts_for_cutoff,
    reconcile_fixture_kickoff_lock,
    select_eligible_from_candidates,
    upcoming_turn_specs,
    window_for_kind,
)
from fantasy_turns.schemas import (
    EnsureFantasyTurnsResponse,
    ExcludeFantasyTurnFixtureRequest,
    FantasyTurnDetailResponse,
    FantasyTurnFixtureResponse,
    FantasyTurnPreviewResponse,
    FantasyTurnSummaryResponse,
    GenerateFantasyTurnRequest,
)
from fantasy_turns.validators import validate_anchor_date, validate_turn_kind
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_competition import LeagueCompetition
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from observability.context import get_correlation_id
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture

logger = get_logger(__name__)
_ = (User, Club)


@dataclass(frozen=True)
class EnsureWindowResult:
    outcome: str  # created | upgraded | duplicate | waiting
    round_id: UUID | None = None
    opened: bool = False


class FantasyTurnService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_turns(self, league_access: LeagueAccess) -> list[FantasyTurnSummaryResponse]:
        now = datetime.now(UTC)
        rounds = self._session.scalars(
            select(FantasyRound)
            .where(FantasyRound.league_id == league_access.league.id)
            .order_by(FantasyRound.number.asc())
        ).all()
        return [self._to_summary(row, now=now) for row in rounds]

    def get_turn(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
        *,
        reconcile_cutoff: bool = True,
    ) -> FantasyTurnDetailResponse:
        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=False)
        now = datetime.now(UTC)
        if reconcile_cutoff and fantasy_round.status != FantasyTurnStatus.SKIPPED:
            changed = self._reconcile_cutoff(
                fantasy_round,
                now=now,
                actor_id=league_access.user.id,
                commit=True,
            )
            if changed:
                fantasy_round = self._load_round(
                    league_access.league.id, round_id, for_update=False
                )
        return self._to_detail(fantasy_round, now=now)

    def preview(
        self,
        league_access: LeagueAccess,
        payload: GenerateFantasyTurnRequest,
    ) -> FantasyTurnPreviewResponse:
        kind = validate_turn_kind(payload.kind)
        anchor = validate_anchor_date(payload.anchor_date)
        window = window_for_kind(kind, anchor)
        rules = self._load_rules(league_access.league.id)
        min_required = rules.min_fixtures_per_round if rules is not None else 25
        candidates = self._load_candidate_fixtures(league_access.league)
        assigned = self._active_assigned_fixture_ids(league_access.league.id)
        selected = select_eligible_from_candidates(
            candidates,
            window,
            already_assigned_ids=assigned,
        )
        threshold = evaluate_threshold(len(selected), min_required)
        cutoff = compute_cutoff([row.kickoff_at for row in selected])
        fixture_payloads = [
            self._fixture_preview_row(
                row.fixture_id, kickoff=row.kickoff_at, status=row.status_short
            )
            for row in selected
        ]
        return FantasyTurnPreviewResponse(
            kind=kind.value,
            windowStartAt=window.start_at,
            windowEndAt=window.end_at,
            timezone=window.timezone,
            eligibleCount=threshold.eligible_count,
            minRequired=threshold.min_required,
            thresholdOk=threshold.ok,
            skipReason=threshold.skip_reason,
            cutoffAt=cutoff,
            fixtures=fixture_payloads,
        )

    def generate(
        self,
        league_access: LeagueAccess,
        payload: GenerateFantasyTurnRequest,
        *,
        persist_skipped: bool = True,
        auto_open: bool = False,
    ) -> FantasyTurnDetailResponse:
        league = self._lock_league(league_access.league.id)
        kind = validate_turn_kind(payload.kind)
        anchor = validate_anchor_date(payload.anchor_date)
        result = self._materialize_window(
            league,
            kind=kind,
            anchor=anchor,
            actor_id=league_access.user.id,
            persist_skipped=persist_skipped,
            auto_open=auto_open,
            raise_on_duplicate=True,
        )
        if result.outcome == "waiting":
            raise ValidationAuthError(
                "Soglia partite non raggiunta e persistenza skipped disabilitata.",
                code="turn_threshold_not_met",
            )
        assert result.round_id is not None
        self._session.commit()
        return self.get_turn(league_access, result.round_id, reconcile_cutoff=False)

    def ensure_upcoming_for_league(
        self,
        league: League,
        *,
        reference_date: date | None = None,
        horizon_days: int = 14,
        auto_open: bool = True,
        actor_id: UUID | None = None,
    ) -> EnsureFantasyTurnsResponse:
        """Idempotently create upcoming weekend/midweek turns from league fixtures."""
        locked = self._lock_league(league.id)
        ref = reference_date or datetime.now(UTC).date()
        system_actor = actor_id or self._league_owner_id(locked.id)
        if system_actor is None:
            raise ValidationAuthError(
                "Impossibile generare turni: la lega non ha un owner.",
                code="league_owner_missing",
            )
        created = opened = upgraded = duplicates = waiting = 0
        for kind, anchor in upcoming_turn_specs(ref, horizon_days=horizon_days):
            result = self._materialize_window(
                locked,
                kind=kind,
                anchor=anchor,
                actor_id=system_actor,
                persist_skipped=False,
                auto_open=auto_open,
                raise_on_duplicate=False,
            )
            if result.outcome == "created":
                created += 1
            elif result.outcome == "upgraded":
                upgraded += 1
            elif result.outcome == "duplicate":
                duplicates += 1
            elif result.outcome == "waiting":
                waiting += 1
            if result.opened:
                opened += 1
        reconciled = self._reconcile_existing_rounds(
            locked.id,
            now=datetime.now(UTC),
            actor_id=system_actor,
        )
        self._session.commit()
        get_metrics().incr("fantasy_turn_ensure_total", labels={"result": "ok"})
        logger.info(
            "fantasy_turns_ensured",
            extra={
                "league_id": str(locked.id),
                "created": created,
                "opened": opened,
                "upgraded": upgraded,
                "duplicates": duplicates,
                "waiting": waiting,
                "reconciled": reconciled,
                "horizon_days": horizon_days,
            },
        )
        return EnsureFantasyTurnsResponse(
            leagueId=str(locked.id),
            created=created,
            opened=opened,
            upgraded=upgraded,
            duplicates=duplicates,
            waiting=waiting,
            horizonDays=horizon_days,
        )

    def ensure_upcoming_for_active_leagues(
        self,
        *,
        reference_date: date | None = None,
        horizon_days: int = 14,
        auto_open: bool = True,
    ) -> dict[str, int]:
        leagues = list(
            self._session.scalars(
                select(League)
                .where(League.state == LeagueState.ACTIVE)
                .order_by(League.created_at.asc())
            ).all()
        )
        totals = {
            "leagues": len(leagues),
            "created": 0,
            "opened": 0,
            "upgraded": 0,
            "duplicates": 0,
            "waiting": 0,
        }
        for league in leagues:
            summary = self.ensure_upcoming_for_league(
                league,
                reference_date=reference_date,
                horizon_days=horizon_days,
                auto_open=auto_open,
                actor_id=None,
            )
            totals["created"] += summary.created
            totals["opened"] += summary.opened
            totals["upgraded"] += summary.upgraded
            totals["duplicates"] += summary.duplicates
            totals["waiting"] += summary.waiting
        return totals

    def ensure_upcoming_for_league_access(
        self,
        league_access: LeagueAccess,
        *,
        horizon_days: int = 14,
        auto_open: bool = True,
    ) -> EnsureFantasyTurnsResponse:
        return self.ensure_upcoming_for_league(
            league_access.league,
            horizon_days=horizon_days,
            auto_open=auto_open,
            actor_id=league_access.user.id,
        )

    def open_turn(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
    ) -> FantasyTurnDetailResponse:
        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=True)
        now = datetime.now(UTC)
        self._open_round(fantasy_round, now=now, actor_id=league_access.user.id)
        self._session.commit()
        get_metrics().incr("fantasy_turn_opened_total", labels={"result": "success"})
        return self._to_detail(fantasy_round, now=now)

    def exclude_fixture(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
        payload: ExcludeFantasyTurnFixtureRequest,
    ) -> FantasyTurnDetailResponse:
        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=True)
        now = datetime.now(UTC)
        assert_modification_allowed(
            stored=fantasy_round.status,
            now=now,
            cutoff_at=fantasy_round.cutoff_at,
        )
        link = self._session.scalars(
            select(FantasyRoundFixture)
            .where(
                FantasyRoundFixture.round_id == fantasy_round.id,
                FantasyRoundFixture.fixture_id == payload.fixture_id,
            )
            .with_for_update()
        ).first()
        if link is None:
            raise ValidationAuthError(
                "Partita non presente nel turno.",
                code="fixture_not_in_turn",
            )
        if link.excluded_at is not None:
            get_metrics().incr(
                "fantasy_turn_fixture_excluded_total",
                labels={"result": "noop"},
            )
            return self._to_detail(fantasy_round, now=now)

        link.excluded_at = now
        link.excluded_by_user_id = league_access.user.id
        self._session.flush()
        self._reconcile_cutoff(
            fantasy_round,
            now=now,
            actor_id=league_access.user.id,
            commit=False,
        )
        self._add_audit(
            league_id=league_access.league.id,
            actor_id=league_access.user.id,
            action=LeagueAuditAction.FANTASY_TURN_FIXTURE_EXCLUDED,
            details={
                "roundId": str(fantasy_round.id),
                "fixtureId": str(payload.fixture_id),
            },
        )
        self._session.commit()
        get_metrics().incr(
            "fantasy_turn_fixture_excluded_total",
            labels={"result": "success"},
        )
        return self.get_turn(league_access, round_id, reconcile_cutoff=False)

    def recalculate_cutoff(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
    ) -> FantasyTurnDetailResponse:
        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=True)
        now = datetime.now(UTC)
        if fantasy_round.status == FantasyTurnStatus.SKIPPED:
            raise ValidationAuthError(
                "Un turno saltato non ha cutoff.",
                code="turn_skipped",
            )
        changed = self._reconcile_cutoff(
            fantasy_round,
            now=now,
            actor_id=league_access.user.id,
            commit=True,
            force_audit=True,
        )
        get_metrics().incr(
            "fantasy_turn_cutoff_recalculated_total",
            labels={"result": "updated" if changed else "noop"},
        )
        return self._to_detail(fantasy_round, now=now)

    def _materialize_window(
        self,
        league: League,
        *,
        kind: FantasyTurnKind,
        anchor: date,
        actor_id: UUID | None,
        persist_skipped: bool,
        auto_open: bool,
        raise_on_duplicate: bool,
    ) -> EnsureWindowResult:
        window = window_for_kind(kind, anchor)
        rules = self._load_rules(league.id)
        min_required = rules.min_fixtures_per_round if rules is not None else 25
        existing = self._session.scalars(
            select(FantasyRound)
            .where(
                FantasyRound.league_id == league.id,
                FantasyRound.window_start_at == window.start_at,
                FantasyRound.window_end_at == window.end_at,
                FantasyRound.kind == kind,
            )
            .with_for_update()
        ).first()

        candidates = self._load_candidate_fixtures(league)
        assigned = self._active_assigned_fixture_ids(league.id)
        selected = select_eligible_from_candidates(
            candidates,
            window,
            already_assigned_ids=assigned,
        )
        threshold = evaluate_threshold(len(selected), min_required)
        now = datetime.now(UTC)

        if existing is not None:
            if existing.status != FantasyTurnStatus.SKIPPED:
                if raise_on_duplicate:
                    get_metrics().incr(
                        "fantasy_turn_generated_total",
                        labels={"result": "duplicate_window"},
                    )
                    raise ValidationAuthError(
                        "Esiste già un turno per questa finestra.",
                        code="turn_window_exists",
                    )
                return EnsureWindowResult(outcome="duplicate", round_id=existing.id)
            if not threshold.ok:
                return EnsureWindowResult(outcome="waiting", round_id=existing.id)
            cutoff = compute_cutoff([row.kickoff_at for row in selected])
            existing.status = FantasyTurnStatus.SCHEDULED
            existing.skip_reason = None
            existing.cutoff_at = cutoff
            existing.generated_at = now
            for row in selected:
                self._session.add(
                    FantasyRoundFixture(
                        round_id=existing.id,
                        league_id=league.id,
                        fixture_id=row.fixture_id,  # type: ignore[arg-type]
                        included_reason=FantasyRoundFixtureReason.WINDOW,
                        observed_kickoff_at=row.kickoff_at,
                    )
                )
            self._add_audit(
                league_id=league.id,
                actor_id=actor_id,
                action=LeagueAuditAction.FANTASY_TURN_GENERATED,
                details={
                    "roundId": str(existing.id),
                    "number": existing.number,
                    "status": FantasyTurnStatus.SCHEDULED.value,
                    "fixtureCount": len(selected),
                    "cutoffAt": cutoff.isoformat() if cutoff else None,
                    "upgradedFromSkipped": True,
                },
            )
            did_open = False
            if auto_open:
                did_open = self._try_auto_open(existing, now=now, actor_id=actor_id)
            self._session.flush()
            get_metrics().incr("fantasy_turn_generated_total", labels={"result": "upgraded"})
            return EnsureWindowResult(
                outcome="upgraded",
                round_id=existing.id,
                opened=did_open,
            )

        if not threshold.ok:
            if not persist_skipped:
                return EnsureWindowResult(outcome="waiting", round_id=None)
            next_number = self._next_round_number(league.id)
            fantasy_round = FantasyRound(
                league_id=league.id,
                number=next_number,
                kind=kind,
                window_start_at=window.start_at,
                window_end_at=window.end_at,
                cutoff_at=None,
                status=FantasyTurnStatus.SKIPPED,
                skip_reason=threshold.skip_reason,
                generated_at=now,
            )
            self._session.add(fantasy_round)
            self._session.flush()
            self._add_audit(
                league_id=league.id,
                actor_id=actor_id,
                action=LeagueAuditAction.FANTASY_TURN_GENERATED,
                details={
                    "roundId": str(fantasy_round.id),
                    "number": next_number,
                    "status": FantasyTurnStatus.SKIPPED.value,
                    "eligibleCount": threshold.eligible_count,
                    "minRequired": threshold.min_required,
                },
            )
            get_metrics().incr("fantasy_turn_generated_total", labels={"result": "skipped"})
            logger.info(
                "fantasy_turn_skipped",
                extra={
                    "league_id": str(league.id),
                    "round_number": next_number,
                    "eligible_count": threshold.eligible_count,
                    "min_required": threshold.min_required,
                },
            )
            self._session.flush()
            return EnsureWindowResult(outcome="created", round_id=fantasy_round.id)

        cutoff = compute_cutoff([row.kickoff_at for row in selected])
        next_number = self._next_round_number(league.id)
        fantasy_round = FantasyRound(
            league_id=league.id,
            number=next_number,
            kind=kind,
            window_start_at=window.start_at,
            window_end_at=window.end_at,
            cutoff_at=cutoff,
            status=FantasyTurnStatus.SCHEDULED,
            skip_reason=None,
            generated_at=now,
        )
        self._session.add(fantasy_round)
        self._session.flush()
        for row in selected:
            self._session.add(
                FantasyRoundFixture(
                    round_id=fantasy_round.id,
                    league_id=league.id,
                    fixture_id=row.fixture_id,  # type: ignore[arg-type]
                    included_reason=FantasyRoundFixtureReason.WINDOW,
                    observed_kickoff_at=row.kickoff_at,
                )
            )
        self._add_audit(
            league_id=league.id,
            actor_id=actor_id,
            action=LeagueAuditAction.FANTASY_TURN_GENERATED,
            details={
                "roundId": str(fantasy_round.id),
                "number": next_number,
                "status": FantasyTurnStatus.SCHEDULED.value,
                "fixtureCount": len(selected),
                "cutoffAt": cutoff.isoformat() if cutoff else None,
            },
        )
        did_open = False
        if auto_open:
            did_open = self._try_auto_open(fantasy_round, now=now, actor_id=actor_id)
        self._session.flush()
        get_metrics().incr("fantasy_turn_generated_total", labels={"result": "success"})
        logger.info(
            "fantasy_turn_generated",
            extra={
                "league_id": str(league.id),
                "round_id": str(fantasy_round.id),
                "round_number": next_number,
                "fixture_count": len(selected),
            },
        )
        return EnsureWindowResult(
            outcome="created",
            round_id=fantasy_round.id,
            opened=did_open,
        )

    def _try_auto_open(
        self,
        fantasy_round: FantasyRound,
        *,
        now: datetime,
        actor_id: UUID | None,
    ) -> bool:
        if fantasy_round.status != FantasyTurnStatus.SCHEDULED:
            return False
        if fantasy_round.cutoff_at is not None and ensure_utc(now) >= ensure_utc(
            fantasy_round.cutoff_at
        ):
            return False
        fantasy_round.status = FantasyTurnStatus.OPEN
        fantasy_round.opens_at = now
        self._add_audit(
            league_id=fantasy_round.league_id,
            actor_id=actor_id,
            action=LeagueAuditAction.FANTASY_TURN_OPENED,
            details={
                "roundId": str(fantasy_round.id),
                "number": fantasy_round.number,
                "auto": True,
            },
        )
        get_metrics().incr("fantasy_turn_opened_total", labels={"result": "auto"})
        return True

    def _open_round(
        self,
        fantasy_round: FantasyRound,
        *,
        now: datetime,
        actor_id: UUID | None,
    ) -> None:
        if fantasy_round.status == FantasyTurnStatus.SKIPPED:
            raise ValidationAuthError(
                "Un turno saltato non può essere aperto.",
                code="turn_skipped",
            )
        if fantasy_round.status == FantasyTurnStatus.OPEN:
            get_metrics().incr("fantasy_turn_opened_total", labels={"result": "noop"})
            return
        if fantasy_round.status == FantasyTurnStatus.LOCKED:
            raise ValidationAuthError(
                "Il turno è già chiuso.",
                code="turn_locked",
            )
        if fantasy_round.status != FantasyTurnStatus.SCHEDULED:
            raise ValidationAuthError(
                "Solo un turno programmato può essere aperto.",
                code="invalid_turn_status",
            )
        self._reconcile_cutoff(fantasy_round, now=now, actor_id=actor_id, commit=False)
        effective = derive_effective_status(
            FantasyTurnStatus.OPEN,
            now=now,
            cutoff_at=fantasy_round.cutoff_at,
        )
        if effective == FantasyTurnStatus.LOCKED:
            raise ValidationAuthError(
                "Il cutoff è già trascorso: impossibile aprire il turno.",
                code="turn_modification_closed",
            )
        fantasy_round.status = FantasyTurnStatus.OPEN
        fantasy_round.opens_at = now
        self._add_audit(
            league_id=fantasy_round.league_id,
            actor_id=actor_id,
            action=LeagueAuditAction.FANTASY_TURN_OPENED,
            details={"roundId": str(fantasy_round.id), "number": fantasy_round.number},
        )

    def _reconcile_cutoff(
        self,
        fantasy_round: FantasyRound,
        *,
        now: datetime,
        actor_id: UUID | None,
        commit: bool,
        force_audit: bool = False,
    ) -> bool:
        active_links = [
            link
            for link in self._load_round_fixtures(fantasy_round.id)
            if link.excluded_at is None and link.fixture is not None
        ]
        fixture_changes: list[dict[str, object]] = []
        live_kickoffs: list[datetime] = []
        for link in active_links:
            fixture = link.fixture
            assert fixture is not None
            previous_observed = link.observed_kickoff_at
            previous_latched = link.lock_latched_at
            state = reconcile_fixture_kickoff_lock(
                now=now,
                current_kickoff_at=fixture.kickoff_at,
                status_short=fixture.status_short,
                observed_kickoff_at=link.observed_kickoff_at,
                lock_latched_at=link.lock_latched_at,
            )
            link.observed_kickoff_at = state.observed_kickoff_at
            link.lock_latched_at = state.lock_latched_at
            if kickoff_counts_for_cutoff(
                kickoff_at=fixture.kickoff_at,
                status_short=fixture.status_short,
                now=now,
            ):
                assert fixture.kickoff_at is not None
                live_kickoffs.append(fixture.kickoff_at)
            if (
                previous_observed != state.observed_kickoff_at
                or previous_latched != state.lock_latched_at
                or state.just_latched
            ):
                fixture_changes.append(
                    {
                        "fixtureId": str(link.fixture_id),
                        "statusShort": fixture.status_short,
                        "previousObservedKickoffAt": (
                            previous_observed.isoformat() if previous_observed else None
                        ),
                        "observedKickoffAt": (
                            state.observed_kickoff_at.isoformat()
                            if state.observed_kickoff_at
                            else None
                        ),
                        "lockLatchedAt": (
                            state.lock_latched_at.isoformat() if state.lock_latched_at else None
                        ),
                        "justLatched": state.just_latched,
                    }
                )

        candidate = compute_cutoff(live_kickoffs)
        previous = fantasy_round.cutoff_at
        new_cutoff = apply_cutoff_recalculation(
            previous_cutoff=previous,
            candidate_cutoff=candidate,
            now=now,
        )
        previous_utc = ensure_utc(previous) if previous is not None else None
        changed = previous_utc != new_cutoff or bool(fixture_changes)
        latched = (
            previous_utc is not None
            and new_cutoff == previous_utc
            and (candidate is None or ensure_utc(candidate) != previous_utc)
            and ensure_utc(now) >= previous_utc
        )
        if not changed and not force_audit:
            return False
        fantasy_round.cutoff_at = new_cutoff
        if fantasy_round.status == FantasyTurnStatus.OPEN and new_cutoff is not None:
            if (
                derive_effective_status(
                    FantasyTurnStatus.OPEN,
                    now=now,
                    cutoff_at=new_cutoff,
                )
                == FantasyTurnStatus.LOCKED
            ):
                fantasy_round.status = FantasyTurnStatus.LOCKED
                if fantasy_round.closes_at is None:
                    fantasy_round.closes_at = now
        if changed or force_audit:
            self._add_audit(
                league_id=fantasy_round.league_id,
                actor_id=actor_id,
                action=LeagueAuditAction.FANTASY_TURN_CUTOFF_RECALCULATED,
                details={
                    "roundId": str(fantasy_round.id),
                    "previousCutoffAt": previous.isoformat() if previous else None,
                    "cutoffAt": new_cutoff.isoformat() if new_cutoff else None,
                    "candidateCutoffAt": candidate.isoformat() if candidate else None,
                    "latched": latched,
                    "fixtureChanges": fixture_changes,
                },
            )
            logger.info(
                "fantasy_turn_cutoff_recalculated",
                extra={
                    "round_id": str(fantasy_round.id),
                    "latched": latched,
                    "changed": changed,
                    "fixture_change_count": len(fixture_changes),
                },
            )
        if commit:
            self._session.commit()
        else:
            self._session.flush()
        return changed

    def _reconcile_existing_rounds(
        self,
        league_id: UUID,
        *,
        now: datetime,
        actor_id: UUID | None,
    ) -> int:
        """Recompute cutoff/lock for persisted turns after provider kickoff changes."""
        rounds = self._session.scalars(
            select(FantasyRound)
            .where(
                FantasyRound.league_id == league_id,
                FantasyRound.status != FantasyTurnStatus.SKIPPED,
            )
            .order_by(FantasyRound.number.asc())
            .with_for_update()
        ).all()
        updated = 0
        for fantasy_round in rounds:
            if self._reconcile_cutoff(
                fantasy_round,
                now=now,
                actor_id=actor_id,
                commit=False,
            ):
                updated += 1
        return updated

    def _load_candidate_fixtures(self, league: League) -> list[EligibleFixtureRef]:
        competition_ids = self._session.scalars(
            select(LeagueCompetition.competition_id).where(LeagueCompetition.league_id == league.id)
        ).all()
        if not competition_ids:
            return []
        season_ids = self._session.scalars(
            select(SportSeason.id).where(
                SportSeason.competition_id.in_(competition_ids),
                SportSeason.year == league.season_year,
            )
        ).all()
        if not season_ids:
            return []
        rows = self._session.execute(
            select(Fixture.id, Fixture.kickoff_at, Fixture.status_short).where(
                Fixture.sport_season_id.in_(season_ids),
                Fixture.kickoff_at.is_not(None),
            )
        ).all()
        result: list[EligibleFixtureRef] = []
        for fixture_id, kickoff_at, status_short in rows:
            if kickoff_at is None:
                continue
            result.append(
                EligibleFixtureRef(
                    fixture_id=fixture_id,
                    kickoff_at=kickoff_at,
                    status_short=status_short,
                )
            )
        return result

    def _active_assigned_fixture_ids(self, league_id: UUID) -> set[UUID]:
        rows = self._session.scalars(
            select(FantasyRoundFixture.fixture_id)
            .join(FantasyRound, FantasyRound.id == FantasyRoundFixture.round_id)
            .where(
                FantasyRound.league_id == league_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
        return set(rows)

    def _league_owner_id(self, league_id: UUID) -> UUID | None:
        return self._session.scalar(
            select(LeagueMembership.user_id).where(
                LeagueMembership.league_id == league_id,
                LeagueMembership.role == LeagueMemberRole.OWNER,
            )
        )

    def _next_round_number(self, league_id: UUID) -> int:
        current = self._session.scalar(
            select(func.max(FantasyRound.number)).where(FantasyRound.league_id == league_id)
        )
        return int(current or 0) + 1

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

    def _load_round(
        self,
        league_id: UUID,
        round_id: UUID,
        *,
        for_update: bool,
    ) -> FantasyRound:
        stmt = select(FantasyRound).where(
            FantasyRound.id == round_id,
            FantasyRound.league_id == league_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        fantasy_round = self._session.scalars(stmt).first()
        if fantasy_round is None:
            raise ValidationAuthError("Turno non trovato.", code="turn_not_found")
        return fantasy_round

    def _load_round_fixtures(self, round_id: UUID) -> list[FantasyRoundFixture]:
        return list(
            self._session.scalars(
                select(FantasyRoundFixture)
                .where(FantasyRoundFixture.round_id == round_id)
                .options(
                    selectinload(FantasyRoundFixture.fixture).selectinload(Fixture.home_club),
                    selectinload(FantasyRoundFixture.fixture).selectinload(Fixture.away_club),
                    selectinload(FantasyRoundFixture.fixture)
                    .selectinload(Fixture.sport_season)
                    .selectinload(SportSeason.competition),
                )
                .order_by(FantasyRoundFixture.created_at.asc())
            ).all()
        )

    def _fixture_preview_row(
        self,
        fixture_id: object,
        *,
        kickoff: datetime,
        status: str,
    ) -> FantasyTurnFixtureResponse:
        fixture = self._session.scalars(
            select(Fixture)
            .where(Fixture.id == fixture_id)  # type: ignore[arg-type]
            .options(
                selectinload(Fixture.home_club),
                selectinload(Fixture.away_club),
                selectinload(Fixture.sport_season).selectinload(SportSeason.competition),
            )
        ).first()
        if fixture is None:
            return FantasyTurnFixtureResponse(
                id=str(fixture_id),
                fixtureId=str(fixture_id),
                includedReason=FantasyRoundFixtureReason.WINDOW.value,
                excludedAt=None,
                kickoffAt=kickoff,
                observedKickoffAt=kickoff,
                lockLatchedAt=None,
                statusShort=status,
                homeClubName="?",
                awayClubName="?",
                competitionName=None,
                providerId=0,
            )
        competition = None
        if fixture.sport_season and fixture.sport_season.competition:
            competition = fixture.sport_season.competition.name
        return FantasyTurnFixtureResponse(
            id=str(fixture.id),
            fixtureId=str(fixture.id),
            includedReason=FantasyRoundFixtureReason.WINDOW.value,
            excludedAt=None,
            kickoffAt=fixture.kickoff_at,
            observedKickoffAt=fixture.kickoff_at,
            lockLatchedAt=None,
            statusShort=fixture.status_short,
            homeClubName=fixture.home_club.name if fixture.home_club else "?",
            awayClubName=fixture.away_club.name if fixture.away_club else "?",
            competitionName=competition,
            providerId=fixture.provider_id,
        )

    def _to_summary(
        self, fantasy_round: FantasyRound, *, now: datetime
    ) -> FantasyTurnSummaryResponse:
        active_count = self._session.scalar(
            select(func.count(FantasyRoundFixture.id)).where(
                FantasyRoundFixture.round_id == fantasy_round.id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        )
        effective = derive_effective_status(
            fantasy_round.status,
            now=now,
            cutoff_at=fantasy_round.cutoff_at,
        )
        return FantasyTurnSummaryResponse(
            id=str(fantasy_round.id),
            leagueId=str(fantasy_round.league_id),
            number=fantasy_round.number,
            kind=fantasy_round.kind.value,
            windowStartAt=fantasy_round.window_start_at,
            windowEndAt=fantasy_round.window_end_at,
            opensAt=fantasy_round.opens_at,
            closesAt=fantasy_round.closes_at,
            cutoffAt=fantasy_round.cutoff_at,
            status=fantasy_round.status.value,
            effectiveStatus=effective.value,
            skipReason=fantasy_round.skip_reason,
            fixtureCount=int(active_count or 0),
            generatedAt=fantasy_round.generated_at,
            modificationAllowed=is_modification_allowed(
                stored=fantasy_round.status,
                now=now,
                cutoff_at=fantasy_round.cutoff_at,
            ),
        )

    def _to_detail(
        self, fantasy_round: FantasyRound, *, now: datetime
    ) -> FantasyTurnDetailResponse:
        summary = self._to_summary(fantasy_round, now=now)
        links = self._load_round_fixtures(fantasy_round.id)
        fixtures = [self._to_fixture_response(link) for link in links if link.excluded_at is None]
        return FantasyTurnDetailResponse(
            id=summary.id,
            leagueId=summary.league_id,
            number=summary.number,
            kind=summary.kind,
            windowStartAt=summary.window_start_at,
            windowEndAt=summary.window_end_at,
            opensAt=summary.opens_at,
            closesAt=summary.closes_at,
            cutoffAt=summary.cutoff_at,
            status=summary.status,
            effectiveStatus=summary.effective_status,
            skipReason=summary.skip_reason,
            fixtureCount=summary.fixture_count,
            generatedAt=summary.generated_at,
            modificationAllowed=summary.modification_allowed,
            homologationStatus=fantasy_round.homologation_status.value,
            fixtures=fixtures,
        )

    @staticmethod
    def _to_fixture_response(link: FantasyRoundFixture) -> FantasyTurnFixtureResponse:
        fixture = link.fixture
        home = fixture.home_club.name if fixture and fixture.home_club else "?"
        away = fixture.away_club.name if fixture and fixture.away_club else "?"
        competition = None
        if fixture and fixture.sport_season and fixture.sport_season.competition:
            competition = fixture.sport_season.competition.name
        return FantasyTurnFixtureResponse(
            id=str(link.id),
            fixtureId=str(link.fixture_id),
            includedReason=link.included_reason.value,
            excludedAt=link.excluded_at,
            kickoffAt=fixture.kickoff_at if fixture else None,
            observedKickoffAt=link.observed_kickoff_at,
            lockLatchedAt=link.lock_latched_at,
            statusShort=fixture.status_short if fixture else "NS",
            statusElapsed=fixture.status_elapsed if fixture else None,
            homeGoals=fixture.home_goals if fixture else None,
            awayGoals=fixture.away_goals if fixture else None,
            homeClubName=home,
            awayClubName=away,
            competitionName=competition,
            providerId=fixture.provider_id if fixture else 0,
        )

    def _add_audit(
        self,
        *,
        league_id: UUID,
        actor_id: UUID | None,
        action: LeagueAuditAction,
        details: dict,
    ) -> None:
        resolved_actor_id = actor_id or self._league_owner_id(league_id)
        if resolved_actor_id is None:
            raise ValidationAuthError(
                "Impossibile registrare l'evento: la lega non ha un owner.",
                code="league_owner_missing",
            )
        self._session.add(
            LeagueAuditEvent(
                league_id=league_id,
                actor_id=resolved_actor_id,
                action=action,
                correlation_id=get_correlation_id(),
                details=details,
            )
        )
