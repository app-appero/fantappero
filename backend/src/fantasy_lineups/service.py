"""Save, copy and draft fantasy lineups for a european turn."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from database.enums import (
    FantasyRole,
    FantasyTurnStatus,
    LeagueAuditAction,
    LineupSlotKind,
    RosterCompositionStatus,
    TacticalMoveStatus,
)
from fantasy_lineups.models import LineupDraft, LineupPlayer, LineupSubmission, TacticalMove
from fantasy_lineups.rules import (
    DEFAULT_LINEUP_LOCK_MARGIN_MINUTES,
    MAX_AUTOMATIC_SUBSTITUTIONS,
    MAX_TACTICAL_MOVES,
    LineupPlayerRef,
    approved_module_catalog,
    assert_bench_order_lock,
    assert_copy_previous_lineup,
    assert_lineup_modification_allowed,
    assert_progressive_lock,
    assert_tactical_move,
    copy_previous_lineup,
    evaluate_lineup,
    is_athlete_kickoff_locked,
    is_lineup_modification_allowed,
    lineup_signature,
    next_unlocked_kickoff,
    parse_module,
    remaining_tactical_moves,
)
from fantasy_lineups.schemas import (
    LineupContextResponse,
    LineupDraftResponse,
    LineupIssueResponse,
    LineupLockCountdownResponse,
    LineupPlayerResponse,
    LineupRosterPlayerResponse,
    ModuleCountsResponse,
    PreviousLineupResponse,
    SavedLineupResponse,
    SaveLineupDraftRequest,
    SaveLineupRequest,
    TacticalMoveResponse,
)
from fantasy_lineups.validators import (
    parse_optional_athlete_ids,
    validate_athlete_id_list,
    validate_module_code,
)
from fantasy_teams.composition_service import resolve_effective_athlete_roles
from fantasy_teams.factory import ensure_team_for_membership, find_team_for_membership
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.rules import derive_effective_status
from fantasy_turns.service import FantasyTurnService
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from observability.context import get_correlation_id
from observability.logging import get_logger
from observability.metrics import get_metrics
from sports_data.catalog.models import SportSeason
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import SquadMembership

logger = get_logger(__name__)


@dataclass(frozen=True)
class _KickoffRef:
    kickoff_at: datetime | None
    status_short: str | None
    lock_latched: bool = False


@dataclass(frozen=True)
class _RosterRow:
    athlete_id: UUID
    athlete_name: str
    role: FantasyRole | None
    slot_index: int


class FantasyLineupService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_my_lineup(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
    ) -> LineupContextResponse:
        now = datetime.now(UTC)
        fantasy_round = self._load_round(league_access.league.id, round_id)
        self._sync_round_kickoffs(
            fantasy_round,
            now=now,
            actor_id=league_access.user.id,
            commit=True,
        )
        membership = self._require_membership(league_access)
        team, created = ensure_team_for_membership(
            self._session,
            membership,
            name=self._default_team_name(league_access),
            actor_id=league_access.user.id,
        )
        if created:
            self._session.commit()
        team = find_team_for_membership(self._session, membership.id, with_slots=True)
        assert team is not None
        roster = self._roster_rows(league_access.league.season_year, team)
        submission = self._load_submission(fantasy_round.id, team.id)
        return self._to_context(
            league_id=league_access.league.id,
            fantasy_round=fantasy_round,
            roster=roster,
            submission=submission,
            now=now,
            season_year=league_access.league.season_year,
            fantasy_team_id=team.id,
        )

    def get_lock_countdown(self, league_access: LeagueAccess) -> LineupLockCountdownResponse:
        """Prossimo blocco per-giocatore della squadra del chiamante (EP-turni-automazione).

        Leggero apposta — nessun round_id in input, si auto-risolve tutto
        come `get_my_team`: turno di riferimento (stessa scelta della pagina
        Turni) → squadra dalla membership → rosa → kickoff per atleta →
        margine di lega → stato + prossimo istante di blocco.
        """
        now = datetime.now(UTC)
        league = league_access.league
        reference = FantasyTurnService(self._session).resolve_reference_round(league.id)
        if reference is None:
            return LineupLockCountdownResponse(
                leagueId=str(league.id),
                state="no_active_turn",
                serverNow=now,
            )
        effective = derive_effective_status(
            reference.status, now=now, cutoff_at=reference.cutoff_at
        )
        base = {
            "leagueId": str(league.id),
            "roundId": str(reference.id),
            "roundNumber": reference.number,
            "roundStatus": effective.value,
            "serverNow": now,
        }
        if effective not in {FantasyTurnStatus.OPEN, FantasyTurnStatus.LOCKED}:
            # Turno non ancora aperto (o saltato): nessuna formazione è
            # schierabile, quindi non serve nemmeno risolvere/creare la
            # squadra — un endpoint di sola lettura chiamato da ogni pagina
            # non deve scrivere dati quando non ce n'è bisogno.
            return LineupLockCountdownResponse(**base, state="turn_not_open")
        membership = self._require_membership(league_access)
        team, created = ensure_team_for_membership(
            self._session,
            membership,
            name=self._default_team_name(league_access),
            actor_id=league_access.user.id,
        )
        if created:
            self._session.commit()
        team = find_team_for_membership(self._session, membership.id, with_slots=True)
        assert team is not None
        roster = self._roster_rows(league.season_year, team)
        if not roster:
            return LineupLockCountdownResponse(**base, state="no_roster")
        kickoffs = self._athlete_kickoffs(
            round_id=reference.id,
            season_year=league.season_year,
            athlete_ids=[row.athlete_id for row in roster],
        )
        margin = self._lineup_lock_margin_for_league(league.id)
        next_lock = next_unlocked_kickoff(
            (
                (ref.kickoff_at, ref.status_short, ref.lock_latched)
                for ref in kickoffs.values()
            ),
            now=now,
            margin_minutes=margin,
        )
        if next_lock is None:
            return LineupLockCountdownResponse(**base, state="no_pending_lock")
        return LineupLockCountdownResponse(**base, state="counting_down", nextLockAt=next_lock)

    def save_my_lineup(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
        payload: SaveLineupRequest,
    ) -> LineupContextResponse:
        now = datetime.now(UTC)
        module_code = validate_module_code(payload.module)
        starter_ids = validate_athlete_id_list(payload.starter_athlete_ids)
        bench_ids = validate_athlete_id_list(payload.bench_athlete_ids)

        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=True)
        try:
            assert_lineup_modification_allowed(stored=fantasy_round.status)
        except ValidationAuthError as exc:
            get_metrics().incr(
                "fantasy_lineup_saved_total",
                labels={"result": exc.code},
            )
            raise
        self._sync_round_kickoffs(
            fantasy_round,
            now=now,
            actor_id=league_access.user.id,
            commit=False,
        )

        membership = self._require_membership(league_access)
        self._lock_team_for_membership(league_access.league.id, membership.id)
        team = find_team_for_membership(self._session, membership.id, with_slots=True)
        assert team is not None

        if team.composition_status != RosterCompositionStatus.VALIDATED:
            get_metrics().incr(
                "fantasy_lineup_saved_total",
                labels={"result": "roster_not_validated"},
            )
            raise ValidationAuthError(
                "La rosa deve essere convalidata prima di schierare la formazione.",
                code="roster_not_validated",
            )

        roster = self._roster_rows(league_access.league.season_year, team)
        roles_by_id = {row.athlete_id: row.role for row in roster}
        roster_ids = [str(row.athlete_id) for row in roster]
        starters = [
            LineupPlayerRef(athlete_id=str(athlete_id), role=roles_by_id.get(athlete_id))
            for athlete_id in starter_ids
        ]
        bench = [
            LineupPlayerRef(athlete_id=str(athlete_id), role=roles_by_id.get(athlete_id))
            for athlete_id in bench_ids
        ]
        evaluation = evaluate_lineup(
            module=module_code,
            starters=starters,
            bench=bench,
            roster_athlete_ids=roster_ids,
        )
        if not evaluation.valid:
            first = evaluation.issues[0]
            get_metrics().incr(
                "fantasy_lineup_saved_total",
                labels={"result": first.code},
            )
            raise ValidationAuthError(first.message, code=first.code)

        kickoffs = self._athlete_kickoffs(
            round_id=fantasy_round.id,
            season_year=league_access.league.season_year,
            athlete_ids=[row.athlete_id for row in roster],
        )
        lock_margin = self._lineup_lock_margin_for_league(league_access.league.id)
        locked_ids = [
            str(row.athlete_id)
            for row in roster
            if self._is_row_locked(row.athlete_id, kickoffs, now, lock_margin)
        ]
        submission = self._load_submission(fantasy_round.id, team.id, for_update=True)
        try:
            assert_progressive_lock(
                previous_slots=self._slots_from_submission(submission),
                proposed_slots=self._slots_from_ids(starter_ids, bench_ids),
                locked_athlete_ids=locked_ids,
            )
            assert_bench_order_lock(
                previous_bench=self._bench_order_from_submission(submission),
                proposed_bench=[str(athlete_id) for athlete_id in bench_ids],
                locked_athlete_ids=locked_ids,
            )
            move_evaluation = assert_tactical_move(
                has_saved_lineup=submission is not None,
                any_athlete_locked=bool(locked_ids),
                moves_used=len(submission.tactical_moves) if submission is not None else 0,
                proposed_module=module_code,
                proposed_starter_ids=[str(athlete_id) for athlete_id in starter_ids],
                proposed_bench_ids=[str(athlete_id) for athlete_id in bench_ids],
                previous_module=submission.module.value if submission is not None else None,
                previous_starter_ids=self._starter_order_from_submission(submission),
                previous_bench_ids=self._bench_order_from_submission(submission),
            )
        except ValidationAuthError as exc:
            get_metrics().incr(
                "fantasy_lineup_saved_total",
                labels={"result": exc.code},
            )
            logger.info("fantasy_lineup_save_rejected", extra={"result": exc.code})
            raise

        if submission is not None and lineup_signature(
            module=module_code,
            starter_ids=[str(athlete_id) for athlete_id in starter_ids],
            bench_ids=[str(athlete_id) for athlete_id in bench_ids],
        ) == lineup_signature(
            module=submission.module.value,
            starter_ids=self._starter_order_from_submission(submission),
            bench_ids=self._bench_order_from_submission(submission),
        ):
            return self._to_context(
                league_id=league_access.league.id,
                fantasy_round=fantasy_round,
                roster=roster,
                submission=submission,
                now=now,
                season_year=league_access.league.season_year,
                fantasy_team_id=team.id,
            )

        module = parse_module(module_code)
        assert module is not None
        previous_module = submission.module.value if submission is not None else None
        previous_payload = (
            {
                "module": submission.module.value,
                "starterAthleteIds": self._starter_order_from_submission(submission),
                "benchAthleteIds": self._bench_order_from_submission(submission),
            }
            if submission is not None
            else None
        )
        proposed_payload = {
            "module": module.value,
            "starterAthleteIds": [str(athlete_id) for athlete_id in starter_ids],
            "benchAthleteIds": [str(athlete_id) for athlete_id in bench_ids],
        }
        if submission is None:
            submission = LineupSubmission(
                league_id=league_access.league.id,
                round_id=fantasy_round.id,
                fantasy_team_id=team.id,
                module=module,
                revision=1,
                submitted_at=now,
                submitted_by_user_id=league_access.user.id,
            )
            self._session.add(submission)
            self._session.flush()
        else:
            submission.module = module
            submission.revision = submission.revision + 1
            submission.submitted_at = now
            submission.submitted_by_user_id = league_access.user.id
            self._session.execute(
                delete(LineupPlayer).where(LineupPlayer.submission_id == submission.id)
            )
            self._session.flush()

        self._insert_players(
            submission_id=submission.id,
            starter_ids=starter_ids,
            bench_ids=bench_ids,
            roles_by_id=roles_by_id,
        )
        if move_evaluation.would_consume:
            sequence = len(submission.tactical_moves) + 1
            self._session.add(
                TacticalMove(
                    submission_id=submission.id,
                    sequence=sequence,
                    status=TacticalMoveStatus.APPLIED,
                    from_payload=previous_payload or proposed_payload,
                    to_payload=proposed_payload,
                    used_at=now,
                    used_by_user_id=league_access.user.id,
                )
            )
            self._add_audit(
                league_id=league_access.league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.FANTASY_TACTICAL_MOVE_APPLIED,
                details={
                    "roundId": str(fantasy_round.id),
                    "fantasyTeamId": str(team.id),
                    "sequence": sequence,
                    "revision": submission.revision,
                    "previousModule": previous_module,
                    "module": module.value,
                },
            )
            get_metrics().incr("fantasy_tactical_move_applied_total")
            logger.info("fantasy_tactical_move_applied", extra={"sequence": sequence})
        self._session.expire(submission, ["players", "tactical_moves"])
        self._add_audit(
            league_id=league_access.league.id,
            actor_id=league_access.user.id,
            action=LeagueAuditAction.FANTASY_LINEUP_SAVED,
            details={
                "roundId": str(fantasy_round.id),
                "fantasyTeamId": str(team.id),
                "module": module.value,
                "revision": submission.revision,
                "previousModule": previous_module,
                "tacticalMoveConsumed": move_evaluation.would_consume,
            },
        )
        self._session.execute(
            delete(LineupDraft).where(
                LineupDraft.round_id == fantasy_round.id,
                LineupDraft.fantasy_team_id == team.id,
            )
        )
        self._session.commit()
        get_metrics().incr("fantasy_lineup_saved_total", labels={"result": "success"})
        logger.info("fantasy_lineup_saved", extra={"result": "success"})

        submission = self._load_submission(fantasy_round.id, team.id)
        return self._to_context(
            league_id=league_access.league.id,
            fantasy_round=fantasy_round,
            roster=roster,
            submission=submission,
            now=now,
            season_year=league_access.league.season_year,
            fantasy_team_id=team.id,
        )

    def copy_previous_to_draft(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
    ) -> LineupContextResponse:
        now = datetime.now(UTC)
        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=True)
        try:
            assert_lineup_modification_allowed(stored=fantasy_round.status)
        except ValidationAuthError as exc:
            get_metrics().incr("fantasy_lineup_copied_total", labels={"result": exc.code})
            raise
        self._sync_round_kickoffs(
            fantasy_round,
            now=now,
            actor_id=league_access.user.id,
            commit=False,
        )

        membership = self._require_membership(league_access)
        self._lock_team_for_membership(league_access.league.id, membership.id)
        team = find_team_for_membership(self._session, membership.id, with_slots=True)
        assert team is not None
        try:
            self._require_validated_roster(team)
        except ValidationAuthError as exc:
            get_metrics().incr("fantasy_lineup_copied_total", labels={"result": exc.code})
            raise

        roster = self._roster_rows(league_access.league.season_year, team)
        previous = self._load_previous_submission(team.id, fantasy_round)
        if previous is None:
            get_metrics().incr(
                "fantasy_lineup_copied_total",
                labels={"result": "previous_lineup_not_found"},
            )
            raise ValidationAuthError(
                "Non c'è una formazione precedente da copiare.",
                code="previous_lineup_not_found",
            )

        kickoffs = self._athlete_kickoffs(
            round_id=fantasy_round.id,
            season_year=league_access.league.season_year,
            athlete_ids=[row.athlete_id for row in roster],
        )
        lock_margin = self._lineup_lock_margin_for_league(league_access.league.id)
        locked_ids = [
            str(row.athlete_id)
            for row in roster
            if self._is_row_locked(row.athlete_id, kickoffs, now, lock_margin)
        ]
        submission = self._load_submission(fantasy_round.id, team.id, for_update=True)
        copied = copy_previous_lineup(
            previous_module=previous.module.value,
            previous_starter_ids=self._starter_order_from_submission(previous),
            previous_bench_ids=self._bench_order_from_submission(previous),
            roster_athlete_ids=[str(row.athlete_id) for row in roster],
            locked_athlete_ids=locked_ids,
            current_confirmed_slots=self._slots_from_submission(submission),
            current_confirmed_bench=self._bench_order_from_submission(submission),
            role_by_athlete_id={str(row.athlete_id): row.role for row in roster},
        )
        try:
            assert_copy_previous_lineup(copied)
        except ValidationAuthError as exc:
            get_metrics().incr("fantasy_lineup_copied_total", labels={"result": exc.code})
            logger.info("fantasy_lineup_copy_rejected", extra={"result": exc.code})
            raise

        self._upsert_draft(
            league_id=league_access.league.id,
            round_id=fantasy_round.id,
            team_id=team.id,
            user_id=league_access.user.id,
            module_code=copied.module,
            starter_ids=[str(item) for item in copied.starter_ids],
            bench_ids=[str(item) for item in copied.bench_ids],
            now=now,
            copy_source_round_id=previous.round_id,
        )
        self._add_audit(
            league_id=league_access.league.id,
            actor_id=league_access.user.id,
            action=LeagueAuditAction.FANTASY_LINEUP_COPIED,
            details={
                "roundId": str(fantasy_round.id),
                "fantasyTeamId": str(team.id),
                "sourceRoundId": str(previous.round_id),
                "module": copied.module,
                "droppedCount": len(copied.dropped_athlete_ids),
                "unavailableCount": len(copied.unavailable_athlete_ids),
            },
        )
        self._session.commit()
        get_metrics().incr("fantasy_lineup_copied_total", labels={"result": "success"})
        logger.info("fantasy_lineup_copied", extra={"result": "success"})
        return self._to_context(
            league_id=league_access.league.id,
            fantasy_round=fantasy_round,
            roster=roster,
            submission=self._load_submission(fantasy_round.id, team.id),
            now=now,
            season_year=league_access.league.season_year,
            fantasy_team_id=team.id,
        )

    def save_my_draft(
        self,
        league_access: LeagueAccess,
        round_id: UUID,
        payload: SaveLineupDraftRequest,
    ) -> LineupContextResponse:
        now = datetime.now(UTC)
        module_code = validate_module_code(payload.module)
        starter_ids = parse_optional_athlete_ids(payload.starter_athlete_ids)
        bench_ids = parse_optional_athlete_ids(payload.bench_athlete_ids)

        fantasy_round = self._load_round(league_access.league.id, round_id, for_update=True)
        try:
            assert_lineup_modification_allowed(stored=fantasy_round.status)
        except ValidationAuthError as exc:
            get_metrics().incr("fantasy_lineup_draft_saved_total", labels={"result": exc.code})
            raise
        self._sync_round_kickoffs(
            fantasy_round,
            now=now,
            actor_id=league_access.user.id,
            commit=False,
        )

        membership = self._require_membership(league_access)
        self._lock_team_for_membership(league_access.league.id, membership.id)
        team = find_team_for_membership(self._session, membership.id, with_slots=True)
        assert team is not None
        try:
            self._require_validated_roster(team)
        except ValidationAuthError as exc:
            get_metrics().incr("fantasy_lineup_draft_saved_total", labels={"result": exc.code})
            raise

        roster = self._roster_rows(league_access.league.season_year, team)
        roles_by_id = {str(row.athlete_id): row.role for row in roster}
        roster_ids = [str(row.athlete_id) for row in roster]
        starters = [
            LineupPlayerRef(
                athlete_id=athlete_id,
                role=roles_by_id.get(athlete_id) if athlete_id else None,
            )
            for athlete_id in starter_ids
        ]
        bench = [
            LineupPlayerRef(
                athlete_id=athlete_id,
                role=roles_by_id.get(athlete_id) if athlete_id else None,
            )
            for athlete_id in bench_ids
        ]
        evaluation = evaluate_lineup(
            module=module_code,
            starters=starters,
            bench=bench,
            roster_athlete_ids=roster_ids,
            strict=False,
        )
        if not evaluation.valid:
            first = evaluation.issues[0]
            get_metrics().incr(
                "fantasy_lineup_draft_saved_total",
                labels={"result": first.code},
            )
            raise ValidationAuthError(first.message, code=first.code)

        kickoffs = self._athlete_kickoffs(
            round_id=fantasy_round.id,
            season_year=league_access.league.season_year,
            athlete_ids=[row.athlete_id for row in roster],
        )
        lock_margin = self._lineup_lock_margin_for_league(league_access.league.id)
        locked_ids = [
            str(row.athlete_id)
            for row in roster
            if self._is_row_locked(row.athlete_id, kickoffs, now, lock_margin)
        ]
        submission = self._load_submission(fantasy_round.id, team.id, for_update=True)
        filled_starters = [item for item in starter_ids if item]
        filled_bench = [item for item in bench_ids if item]
        try:
            assert_progressive_lock(
                previous_slots=self._slots_from_submission(submission),
                proposed_slots=self._slots_from_ids(
                    [UUID(item) for item in filled_starters],
                    [UUID(item) for item in filled_bench],
                ),
                locked_athlete_ids=locked_ids,
            )
            assert_bench_order_lock(
                previous_bench=self._bench_order_from_submission(submission),
                proposed_bench=filled_bench,
                locked_athlete_ids=locked_ids,
            )
        except ValidationAuthError as exc:
            get_metrics().incr(
                "fantasy_lineup_draft_saved_total",
                labels={"result": exc.code},
            )
            logger.info("fantasy_lineup_draft_rejected", extra={"result": exc.code})
            raise

        self._upsert_draft(
            league_id=league_access.league.id,
            round_id=fantasy_round.id,
            team_id=team.id,
            user_id=league_access.user.id,
            module_code=module_code,
            starter_ids=starter_ids,
            bench_ids=bench_ids,
            now=now,
            copy_source_round_id=None,
        )
        self._add_audit(
            league_id=league_access.league.id,
            actor_id=league_access.user.id,
            action=LeagueAuditAction.FANTASY_LINEUP_DRAFT_SAVED,
            details={
                "roundId": str(fantasy_round.id),
                "fantasyTeamId": str(team.id),
                "module": module_code,
            },
        )
        self._session.commit()
        get_metrics().incr("fantasy_lineup_draft_saved_total", labels={"result": "success"})
        logger.info("fantasy_lineup_draft_saved", extra={"result": "success"})
        return self._to_context(
            league_id=league_access.league.id,
            fantasy_round=fantasy_round,
            roster=roster,
            submission=self._load_submission(fantasy_round.id, team.id),
            now=now,
            season_year=league_access.league.season_year,
            fantasy_team_id=team.id,
        )

    def _insert_players(
        self,
        *,
        submission_id: UUID,
        starter_ids: list[UUID],
        bench_ids: list[UUID],
        roles_by_id: dict[UUID, FantasyRole | None],
    ) -> None:
        rows: list[LineupPlayer] = []
        for index, athlete_id in enumerate(starter_ids):
            role = roles_by_id[athlete_id]
            assert role is not None
            rows.append(
                LineupPlayer(
                    submission_id=submission_id,
                    athlete_id=athlete_id,
                    slot_kind=LineupSlotKind.STARTER,
                    role=role,
                    sort_order=index,
                )
            )
        for index, athlete_id in enumerate(bench_ids):
            role = roles_by_id[athlete_id]
            assert role is not None
            rows.append(
                LineupPlayer(
                    submission_id=submission_id,
                    athlete_id=athlete_id,
                    slot_kind=LineupSlotKind.BENCH,
                    role=role,
                    sort_order=index,
                )
            )
        self._session.add_all(rows)
        self._session.flush()

    def _roster_rows(self, season_year: int, team: FantasyTeam) -> list[_RosterRow]:
        athlete_ids = [
            slot.athlete_id
            for slot in team.slots
            if slot.athlete_id is not None and slot.athlete is not None
        ]
        effective_roles = resolve_effective_athlete_roles(
            self._session,
            league_id=team.league_id,
            athlete_ids=athlete_ids,
            season_year=season_year,
        )
        rows: list[_RosterRow] = []
        for slot in sorted(team.slots, key=lambda item: item.slot_index):
            if slot.athlete_id is None or slot.athlete is None:
                continue
            resolved = effective_roles.get(slot.athlete_id)
            rows.append(
                _RosterRow(
                    athlete_id=slot.athlete_id,
                    athlete_name=slot.athlete.canonical_name,
                    role=resolved.role if resolved is not None else None,
                    slot_index=slot.slot_index,
                )
            )
        return rows

    def _to_context(
        self,
        *,
        league_id: UUID,
        fantasy_round: FantasyRound,
        roster: list[_RosterRow],
        submission: LineupSubmission | None,
        now: datetime,
        season_year: int,
        fantasy_team_id: UUID,
    ) -> LineupContextResponse:
        effective = derive_effective_status(
            fantasy_round.status,
            now=now,
            cutoff_at=fantasy_round.cutoff_at,
        )
        kickoffs = self._athlete_kickoffs(
            round_id=fantasy_round.id,
            season_year=season_year,
            athlete_ids=[row.athlete_id for row in roster],
        )
        lock_margin = self._lineup_lock_margin_for_league(league_id)
        locked_flags = {
            row.athlete_id: self._is_row_locked(row.athlete_id, kickoffs, now, lock_margin)
            for row in roster
        }
        any_unlocked = any(not locked for locked in locked_flags.values()) if roster else True
        turn_editable = is_lineup_modification_allowed(stored=fantasy_round.status)
        issues: list[LineupIssueResponse] = []
        saved: SavedLineupResponse | None = None
        if submission is not None:
            saved = self._to_saved(submission)
            starters = [
                LineupPlayerRef(
                    athlete_id=player.athlete_id,
                    role=self._parse_role(player.role),
                )
                for player in saved.starters
            ]
            bench = [
                LineupPlayerRef(
                    athlete_id=player.athlete_id,
                    role=self._parse_role(player.role),
                )
                for player in saved.bench
            ]
            evaluation = evaluate_lineup(
                module=saved.module,
                starters=starters,
                bench=bench,
                roster_athlete_ids=[str(row.athlete_id) for row in roster],
            )
            issues = [
                LineupIssueResponse(code=item.code, message=item.message)
                for item in evaluation.issues
            ]
        max_automatic_substitutions = self._max_automatic_substitutions_for_league(league_id)
        moves = list(submission.tactical_moves) if submission is not None else []
        moves.sort(key=lambda row: row.sequence)
        used = len(moves)
        locked_ids = [str(row.athlete_id) for row in roster if locked_flags[row.athlete_id]]
        previous = self._load_previous_submission(fantasy_team_id, fantasy_round)
        draft = self._load_draft(fantasy_round.id, fantasy_team_id)
        copy_preview = None
        if previous is not None:
            copy_preview = copy_previous_lineup(
                previous_module=previous.module.value,
                previous_starter_ids=self._starter_order_from_submission(previous),
                previous_bench_ids=self._bench_order_from_submission(previous),
                roster_athlete_ids=[str(row.athlete_id) for row in roster],
                locked_athlete_ids=locked_ids,
                current_confirmed_slots=self._slots_from_submission(submission),
                current_confirmed_bench=self._bench_order_from_submission(submission),
                role_by_athlete_id={str(row.athlete_id): row.role for row in roster},
            )
        copy_issues = (
            [
                LineupIssueResponse(code=item.code, message=item.message)
                for item in copy_preview.issues
            ]
            if copy_preview is not None
            else []
        )
        copy_available = (
            previous is not None
            and turn_editable
            and any_unlocked
            and (copy_preview is None or not copy_preview.blocked)
        )
        return LineupContextResponse(
            leagueId=str(league_id),
            roundId=str(fantasy_round.id),
            roundNumber=fantasy_round.number,
            kind=fantasy_round.kind.value,
            cutoffAt=fantasy_round.cutoff_at,
            status=fantasy_round.status.value,
            effectiveStatus=effective.value,
            modificationAllowed=turn_editable and any_unlocked,
            serverNow=now,
            maxAutomaticSubstitutions=max_automatic_substitutions,
            lineupLockMarginMinutes=lock_margin,
            maxTacticalMoves=MAX_TACTICAL_MOVES,
            tacticalMovesUsed=used,
            tacticalMovesRemaining=remaining_tactical_moves(used=used),
            tacticalMoves=[self._to_tactical_move(row) for row in moves],
            modules=[
                ModuleCountsResponse(
                    code=item.code.value,
                    goalkeepers=item.goalkeepers,
                    defenders=item.defenders,
                    midfielders=item.midfielders,
                    forwards=item.forwards,
                )
                for item in approved_module_catalog()
            ],
            roster=[
                LineupRosterPlayerResponse(
                    athleteId=str(row.athlete_id),
                    athleteName=row.athlete_name,
                    role=row.role.value if row.role is not None else None,
                    slotIndex=row.slot_index,
                    locked=locked_flags[row.athlete_id],
                    lockLatched=(
                        kickoffs[row.athlete_id].lock_latched
                        if row.athlete_id in kickoffs
                        else False
                    ),
                    kickoffAt=(
                        kickoffs[row.athlete_id].kickoff_at if row.athlete_id in kickoffs else None
                    ),
                    fixtureStatus=(
                        kickoffs[row.athlete_id].status_short
                        if row.athlete_id in kickoffs
                        else None
                    ),
                )
                for row in roster
            ],
            lineup=saved,
            previousLineup=self._to_previous(previous) if previous is not None else None,
            draft=self._to_draft(draft) if draft is not None else None,
            copyAvailable=copy_available,
            copyIssues=copy_issues,
            issues=issues,
        )

    def _athlete_kickoffs(
        self,
        *,
        round_id: UUID,
        season_year: int,
        athlete_ids: list[UUID],
    ) -> dict[UUID, _KickoffRef]:
        if not athlete_ids:
            return {}
        links = self._session.scalars(
            select(FantasyRoundFixture)
            .options(selectinload(FantasyRoundFixture.fixture))
            .where(
                FantasyRoundFixture.round_id == round_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
        fixture_by_club: dict[UUID, tuple[Fixture, FantasyRoundFixture]] = {}
        for link in links:
            fixture = link.fixture
            if fixture is None:
                continue
            for club_id in (fixture.home_club_id, fixture.away_club_id):
                current = fixture_by_club.get(club_id)
                if current is None:
                    fixture_by_club[club_id] = (fixture, link)
                    continue
                current_fixture = current[0]
                if fixture.kickoff_at is None:
                    continue
                current_kickoff = current_fixture.kickoff_at
                if current_kickoff is None or fixture.kickoff_at < current_kickoff:
                    fixture_by_club[club_id] = (fixture, link)

        club_by_athlete: dict[UUID, UUID] = {}
        assignments = self._session.scalars(
            select(RoleAssignment).where(
                RoleAssignment.athlete_id.in_(athlete_ids),
                RoleAssignment.season_year == season_year,
            )
        ).all()
        for assignment in assignments:
            if assignment.club_id is not None:
                club_by_athlete[assignment.athlete_id] = assignment.club_id

        missing = [athlete_id for athlete_id in athlete_ids if athlete_id not in club_by_athlete]
        if missing:
            memberships = self._session.scalars(
                select(SquadMembership)
                .join(SportSeason, SquadMembership.sport_season_id == SportSeason.id)
                .where(
                    SquadMembership.athlete_id.in_(missing),
                    SquadMembership.is_active.is_(True),
                    SquadMembership.ended_at.is_(None),
                    SportSeason.year == season_year,
                )
            ).all()
            for membership in memberships:
                club_by_athlete.setdefault(membership.athlete_id, membership.club_id)

        result: dict[UUID, _KickoffRef] = {}
        for athlete_id, club_id in club_by_athlete.items():
            mapped = fixture_by_club.get(club_id)
            if mapped is None:
                continue
            fixture, link = mapped
            result[athlete_id] = _KickoffRef(
                kickoff_at=fixture.kickoff_at,
                status_short=fixture.status_short,
                lock_latched=link.lock_latched_at is not None,
            )
        return result

    @staticmethod
    def _is_row_locked(
        athlete_id: UUID,
        kickoffs: dict[UUID, _KickoffRef],
        now: datetime,
        margin_minutes: int,
    ) -> bool:
        ref = kickoffs.get(athlete_id)
        if ref is None:
            return False
        return is_athlete_kickoff_locked(
            now=now,
            kickoff_at=ref.kickoff_at,
            status_short=ref.status_short,
            lock_latched=ref.lock_latched,
            margin_minutes=margin_minutes,
        )

    def _lineup_lock_margin_for_league(self, league_id: UUID) -> int:
        margin = self._session.execute(
            select(LeagueRules.lineup_lock_margin_minutes).where(
                LeagueRules.league_id == league_id
            )
        ).scalar_one_or_none()
        return margin if margin is not None else DEFAULT_LINEUP_LOCK_MARGIN_MINUTES

    def _max_automatic_substitutions_for_league(self, league_id: UUID) -> int:
        rules = self._session.execute(
            select(LeagueRules.max_automatic_substitutions).where(
                LeagueRules.league_id == league_id
            )
        ).scalar_one_or_none()
        return rules if rules is not None else MAX_AUTOMATIC_SUBSTITUTIONS

    def _sync_round_kickoffs(
        self,
        fantasy_round: FantasyRound,
        *,
        now: datetime,
        actor_id: UUID,
        commit: bool,
    ) -> None:
        if fantasy_round.status == FantasyTurnStatus.SKIPPED:
            return
        FantasyTurnService(self._session)._reconcile_cutoff(
            fantasy_round,
            now=now,
            actor_id=actor_id,
            commit=commit,
        )

    @staticmethod
    def _slots_from_ids(starter_ids: list[UUID], bench_ids: list[UUID]) -> dict[str, str]:
        slots: dict[str, str] = {}
        for athlete_id in starter_ids:
            slots[str(athlete_id)] = LineupSlotKind.STARTER.value
        for athlete_id in bench_ids:
            slots[str(athlete_id)] = LineupSlotKind.BENCH.value
        return slots

    @staticmethod
    def _slots_from_submission(submission: LineupSubmission | None) -> dict[str, str]:
        if submission is None:
            return {}
        return {str(player.athlete_id): player.slot_kind.value for player in submission.players}

    @staticmethod
    def _starter_order_from_submission(submission: LineupSubmission | None) -> list[str]:
        if submission is None:
            return []
        starters = [
            player for player in submission.players if player.slot_kind == LineupSlotKind.STARTER
        ]
        starters.sort(key=lambda row: row.sort_order)
        return [str(player.athlete_id) for player in starters]

    @staticmethod
    def _bench_order_from_submission(submission: LineupSubmission | None) -> list[str]:
        if submission is None:
            return []
        bench = [
            player for player in submission.players if player.slot_kind == LineupSlotKind.BENCH
        ]
        bench.sort(key=lambda row: row.sort_order)
        return [str(player.athlete_id) for player in bench]

    @staticmethod
    def _parse_role(value: str) -> FantasyRole | None:
        try:
            return FantasyRole(value)
        except ValueError:
            return None

    def _to_saved(self, submission: LineupSubmission) -> SavedLineupResponse:
        starters: list[LineupPlayerResponse] = []
        bench: list[LineupPlayerResponse] = []
        ordered = sorted(
            submission.players,
            key=lambda row: (0 if row.slot_kind == LineupSlotKind.STARTER else 1, row.sort_order),
        )
        for row in ordered:
            item = LineupPlayerResponse(
                athleteId=str(row.athlete_id),
                athleteName=row.athlete.canonical_name if row.athlete else "",
                role=row.role.value,
                slotKind=row.slot_kind.value,
                sortOrder=row.sort_order,
            )
            if row.slot_kind == LineupSlotKind.STARTER:
                starters.append(item)
            else:
                bench.append(item)
        starters.sort(key=lambda item: item.sort_order)
        bench.sort(key=lambda item: item.sort_order)
        return SavedLineupResponse(
            id=str(submission.id),
            module=submission.module.value,
            revision=submission.revision,
            submittedAt=submission.submitted_at,
            systemGeneratedAi=submission.system_generated_ai,
            aiAlgorithmVersion=submission.ai_algorithm_version,
            aiDecidedAt=submission.ai_decided_at,
            autoResolutionSource=(
                submission.auto_resolution_source.value
                if submission.auto_resolution_source
                else None
            ),
            starters=starters,
            bench=bench,
        )

    def _to_previous(self, submission: LineupSubmission) -> PreviousLineupResponse:
        saved = self._to_saved(submission)
        round_number = submission.round.number if submission.round is not None else 0
        return PreviousLineupResponse(
            roundId=str(submission.round_id),
            roundNumber=round_number,
            module=saved.module,
            starters=saved.starters,
            bench=saved.bench,
        )

    def _to_draft(self, draft: LineupDraft) -> LineupDraftResponse:
        copy_number = None
        if draft.copy_source_round_id is not None:
            source = self._session.get(FantasyRound, draft.copy_source_round_id)
            copy_number = source.number if source is not None else None
        return LineupDraftResponse(
            module=draft.module.value,
            starterAthleteIds=self._stringify_ids(draft.starter_athlete_ids),
            benchAthleteIds=self._stringify_ids(draft.bench_athlete_ids),
            savedAt=draft.saved_at,
            copySourceRoundId=(
                str(draft.copy_source_round_id) if draft.copy_source_round_id is not None else None
            ),
            copySourceRoundNumber=copy_number,
        )

    @staticmethod
    def _stringify_ids(values: object) -> list[str]:
        if not isinstance(values, list):
            return []
        result: list[str] = []
        for item in values:
            if item in {None, ""}:
                result.append("")
            else:
                result.append(str(item))
        return result

    def _require_validated_roster(self, team: FantasyTeam) -> None:
        if team.composition_status == RosterCompositionStatus.VALIDATED:
            return
        raise ValidationAuthError(
            "La rosa deve essere convalidata prima di schierare la formazione.",
            code="roster_not_validated",
        )

    def _upsert_draft(
        self,
        *,
        league_id: UUID,
        round_id: UUID,
        team_id: UUID,
        user_id: UUID,
        module_code: str,
        starter_ids: list[str],
        bench_ids: list[str],
        now: datetime,
        copy_source_round_id: UUID | None,
    ) -> LineupDraft:
        module = parse_module(module_code)
        assert module is not None
        draft = self._load_draft(round_id, team_id, for_update=True)
        if draft is None:
            draft = LineupDraft(
                league_id=league_id,
                round_id=round_id,
                fantasy_team_id=team_id,
                module=module,
                starter_athlete_ids=starter_ids,
                bench_athlete_ids=bench_ids,
                saved_at=now,
                saved_by_user_id=user_id,
                copy_source_round_id=copy_source_round_id,
            )
            self._session.add(draft)
        else:
            draft.module = module
            draft.starter_athlete_ids = starter_ids
            draft.bench_athlete_ids = bench_ids
            draft.saved_at = now
            draft.saved_by_user_id = user_id
            draft.copy_source_round_id = copy_source_round_id
        self._session.flush()
        return draft

    def _load_previous_submission(
        self,
        team_id: UUID,
        current_round: FantasyRound,
    ) -> LineupSubmission | None:
        stmt = (
            select(LineupSubmission)
            .join(FantasyRound, LineupSubmission.round_id == FantasyRound.id)
            .where(
                LineupSubmission.fantasy_team_id == team_id,
                FantasyRound.league_id == current_round.league_id,
                FantasyRound.number < current_round.number,
            )
            .options(
                selectinload(LineupSubmission.players).selectinload(LineupPlayer.athlete),
                selectinload(LineupSubmission.round),
            )
            .order_by(FantasyRound.number.desc())
        )
        return self._session.scalars(stmt).first()

    def _load_draft(
        self,
        round_id: UUID,
        team_id: UUID,
        *,
        for_update: bool = False,
    ) -> LineupDraft | None:
        stmt = select(LineupDraft).where(
            LineupDraft.round_id == round_id,
            LineupDraft.fantasy_team_id == team_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self._session.scalars(stmt).first()

    @staticmethod
    def _to_tactical_move(row: TacticalMove) -> TacticalMoveResponse:
        from_payload = row.from_payload if isinstance(row.from_payload, dict) else {}
        to_payload = row.to_payload if isinstance(row.to_payload, dict) else {}
        return TacticalMoveResponse(
            sequence=row.sequence,
            status=row.status.value,
            usedAt=row.used_at,
            fromModule=str(from_payload.get("module") or ""),
            toModule=str(to_payload.get("module") or ""),
        )

    def _load_round(
        self,
        league_id: UUID,
        round_id: UUID,
        *,
        for_update: bool = False,
    ) -> FantasyRound:
        stmt = select(FantasyRound).where(
            FantasyRound.id == round_id,
            FantasyRound.league_id == league_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        row = self._session.scalars(stmt).first()
        if row is None:
            raise ValidationAuthError("Turno non trovato.", code="turn_not_found")
        return row

    def _load_submission(
        self,
        round_id: UUID,
        team_id: UUID,
        *,
        for_update: bool = False,
    ) -> LineupSubmission | None:
        stmt = select(LineupSubmission).where(
            LineupSubmission.round_id == round_id,
            LineupSubmission.fantasy_team_id == team_id,
        )
        stmt = stmt.options(
            selectinload(LineupSubmission.players).selectinload(LineupPlayer.athlete),
            selectinload(LineupSubmission.tactical_moves),
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self._session.scalars(stmt).first()

    def _require_membership(self, league_access: LeagueAccess) -> LeagueMembership:
        membership = self._session.scalar(
            select(LeagueMembership).where(
                LeagueMembership.league_id == league_access.league.id,
                LeagueMembership.user_id == league_access.user.id,
            )
        )
        if membership is None:
            raise ValidationAuthError(
                "Devi essere partecipante della lega per gestire la formazione.",
                code="membership_required",
            )
        return membership

    def _lock_team_for_membership(self, league_id: UUID, membership_id: UUID) -> FantasyTeam:
        team = self._session.scalars(
            select(FantasyTeam)
            .where(
                FantasyTeam.league_id == league_id,
                FantasyTeam.membership_id == membership_id,
            )
            .with_for_update()
        ).first()
        if team is None:
            raise ValidationAuthError("Squadra non trovata.", code="fantasy_team_not_found")
        return team

    def _default_team_name(self, league_access: LeagueAccess) -> str:
        return (league_access.user.display_name or "Squadra")[:120]

    def _add_audit(
        self,
        *,
        league_id: UUID,
        actor_id: UUID,
        action: LeagueAuditAction,
        details: dict,
    ) -> None:
        self._session.add(
            LeagueAuditEvent(
                league_id=league_id,
                actor_id=actor_id,
                action=action,
                correlation_id=get_correlation_id(),
                details=details,
            )
        )
