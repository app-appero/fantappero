"""League domain services (EP02-03 / EP03-01)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from authorization.context import LeagueAccess
from authorization.service import AuthorizationService
from database.enums import (
    LeagueAuditAction,
    LeagueMemberRole,
    LeagueState,
    league_member_role_to_league_role,
)
from fantasy_lineups.rules import STANDARD_AUTOMATIC_SUBSTITUTIONS
from fantasy_ratings.eligibility import STANDARD_MINUTES_THRESHOLD
from fantasy_teams.composition_service import activation_roster_and_credit_blockers
from fantasy_teams.factory import ensure_team_for_membership
from fantasy_teams.ledger import find_account_for_team
from fantasy_turns.rules import STANDARD_MIN_FIXTURES
from fantasy_turns.validators import validate_min_fixtures_per_round
from leagues.calendar_service import league_has_confirmed_calendar
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.schemas import (
    CompetitionSummaryResponse,
    CreateLeagueRequest,
    LeagueAdminPanelResponse,
    LeagueDetailResponse,
    LeagueLifecycleBlocker,
    LeagueLifecycleResponse,
    LeagueRosterConfig,
    LeagueRulesOptions,
    LeagueRulesResponse,
    LeagueSummaryResponse,
    TransitionLeagueStateRequest,
    UpdateLeagueRulesRequest,
)
from leagues.validators import (
    LEAGUE_TRANSITIONS,
    MAX_PARTICIPANTS,
    MIN_PARTICIPANTS,
    STANDARD_DEFENDERS,
    STANDARD_FORWARDS,
    STANDARD_GOALKEEPERS,
    STANDARD_MIDFIELDERS,
    STANDARD_PARTICIPANT_COUNT,
    STANDARD_PRESET_NAME,
    STANDARD_ROSTER_SIZE,
    STANDARD_TOTAL_CREDITS,
    auction_activation_blockers,
    configuration_blockers,
    validate_competition_ids,
    validate_configurable_league_state,
    validate_league_deletable,
    validate_league_name,
    validate_league_transition,
    validate_max_automatic_substitutions,
    validate_minutes_threshold,
    validate_participant_count,
    validate_preset_name,
    validate_season_year,
    validate_standard_roster,
    validate_total_credits,
)
from observability.context import get_correlation_id
from observability.logging import get_logger
from observability.metrics import get_metrics

logger = get_logger(__name__)


class LeagueService:
    def __init__(self, session: Session, authz: AuthorizationService) -> None:
        self._session = session
        self._authz = authz

    def list_competitions(self) -> list[CompetitionSummaryResponse]:
        rows = self._session.scalars(
            select(Competition).order_by(Competition.name.asc()),
        ).all()
        return [self._to_competition_summary(row) for row in rows]

    def create_league(self, user: User, payload: CreateLeagueRequest) -> LeagueDetailResponse:
        name = validate_league_name(payload.name)
        season_year = validate_season_year(payload.season_year)
        competition_ids = validate_competition_ids(payload.competition_ids)

        competitions = self._session.scalars(
            select(Competition).where(Competition.id.in_(competition_ids)),
        ).all()
        if len(competitions) != len(competition_ids):
            raise ValidationAuthError(
                "Uno o più campionati selezionati non sono validi.",
                code="invalid_competition_ids",
            )

        league = League(
            name=name,
            season_year=season_year,
            state=LeagueState.DRAFT,
        )
        self._session.add(league)
        self._session.flush()

        membership = LeagueMembership(
            league_id=league.id,
            user_id=user.id,
            role=LeagueMemberRole.OWNER,
        )
        self._session.add(membership)
        self._session.add(
            LeagueRules(
                league_id=league.id,
                preset_name=STANDARD_PRESET_NAME,
                participant_count=STANDARD_PARTICIPANT_COUNT,
                roster_size=STANDARD_ROSTER_SIZE,
                goalkeepers=STANDARD_GOALKEEPERS,
                defenders=STANDARD_DEFENDERS,
                midfielders=STANDARD_MIDFIELDERS,
                forwards=STANDARD_FORWARDS,
                total_credits=STANDARD_TOTAL_CREDITS,
                min_fixtures_per_round=STANDARD_MIN_FIXTURES,
                minutes_threshold=STANDARD_MINUTES_THRESHOLD,
                max_automatic_substitutions=STANDARD_AUTOMATIC_SUBSTITUTIONS,
                allow_trades=True,
                allow_manual_invites=True,
            ),
        )
        league.competitions = list(competitions)
        self._session.flush()

        team, created = ensure_team_for_membership(
            self._session,
            membership,
            name=user.display_name,
            roster_size=STANDARD_ROSTER_SIZE,
            actor_id=user.id,
        )
        if created:
            self._session.add(
                LeagueAuditEvent(
                    league_id=league.id,
                    actor_id=user.id,
                    action=LeagueAuditAction.FANTASY_TEAM_CREATED,
                    correlation_id=get_correlation_id(),
                    details={"fantasyTeamId": str(team.id), "membershipId": str(membership.id)},
                ),
            )
            account = find_account_for_team(self._session, team.id)
            if account is not None:
                self._session.add(
                    LeagueAuditEvent(
                        league_id=league.id,
                        actor_id=user.id,
                        action=LeagueAuditAction.CREDIT_ACCOUNT_INITIALIZED,
                        correlation_id=get_correlation_id(),
                        details={
                            "fantasyTeamId": str(team.id),
                            "balance": account.balance,
                        },
                    ),
                )

        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=user.id,
                action=LeagueAuditAction.LEAGUE_CREATED,
                correlation_id=get_correlation_id(),
            ),
        )
        self._session.commit()

        get_metrics().incr("league_created_total", labels={"result": "success"})
        return self._to_league_detail(
            league,
            viewer_role=league_member_role_to_league_role(LeagueMemberRole.OWNER).value,
        )

    def list_user_leagues(self, user_id: UUID) -> list[LeagueSummaryResponse]:
        memberships = self._authz.list_memberships_for_user(user_id)
        return [
            LeagueSummaryResponse(
                id=str(membership.league_id),
                name=membership.league.name,
                role=league_member_role_to_league_role(membership.role).value,
                state=membership.league.state,
            )
            for membership in memberships
        ]

    def get_league_detail(self, league_access: LeagueAccess) -> LeagueDetailResponse:
        league = self._load_league_with_competitions(league_access.league.id)
        viewer_role = (
            league_member_role_to_league_role(league_access.membership_role).value
            if league_access.membership_role is not None
            else None
        )
        return self._to_league_detail(league, viewer_role=viewer_role)

    def get_admin_panel(self, league_access: LeagueAccess) -> LeagueAdminPanelResponse:
        league = self._load_league_with_competitions(league_access.league.id)
        rules = self._resolve_rules_for_league(league)
        return LeagueAdminPanelResponse(
            league_id=str(league_access.league.id),
            message="Configura il regolamento della lega prima dell'avvio.",
            rules=self._to_rules_response(rules),
            lifecycle=self._to_lifecycle_response(league),
        )

    def transition_state(
        self,
        league_access: LeagueAccess,
        payload: TransitionLeagueStateRequest,
    ) -> LeagueLifecycleResponse:
        league = self._lock_league_for_lifecycle(league_access.league.id)
        before = league.state
        if not validate_league_transition(before, payload.target_state):
            response = self._to_lifecycle_response(league)
            self._session.commit()
            self._record_transition_result("noop", before, payload.target_state)
            return response

        current_lifecycle = self._to_lifecycle_response(league)
        if payload.target_state not in current_lifecycle.allowed_transitions:
            self._record_transition_result("blocked", before, payload.target_state)
            message = (
                current_lifecycle.blockers[0].message
                if current_lifecycle.blockers
                else "La transizione non può essere completata."
            )
            raise ValidationAuthError(message, code="league_transition_blocked")

        league.state = payload.target_state
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_STATE_CHANGED,
                correlation_id=get_correlation_id(),
                details={"before": before.value, "after": payload.target_state.value},
            )
        )
        response = self._to_lifecycle_response(league)
        self._session.commit()
        self._record_transition_result("success", before, payload.target_state)
        return response

    def update_rules(
        self,
        league_access: LeagueAccess,
        payload: UpdateLeagueRulesRequest,
    ) -> LeagueRulesResponse:
        league = self._load_league_with_competitions(league_access.league.id)
        validate_configurable_league_state(league.state, subject="il regolamento")

        preset_name = validate_preset_name(payload.preset_name)
        participant_count = validate_participant_count(payload.participant_count)
        total_credits = validate_total_credits(payload.total_credits)
        validate_standard_roster(
            roster_size=payload.roster.roster_size,
            goalkeepers=payload.roster.goalkeepers,
            defenders=payload.roster.defenders,
            midfielders=payload.roster.midfielders,
            forwards=payload.roster.forwards,
        )

        rules = self._resolve_rules_for_league(league)
        min_fixtures = (
            validate_min_fixtures_per_round(payload.min_fixtures_per_round)
            if payload.min_fixtures_per_round is not None
            else rules.min_fixtures_per_round
        )
        minutes_threshold = (
            validate_minutes_threshold(payload.minutes_threshold)
            if payload.minutes_threshold is not None
            else rules.minutes_threshold
        )
        max_automatic_substitutions = (
            validate_max_automatic_substitutions(payload.max_automatic_substitutions)
            if payload.max_automatic_substitutions is not None
            else rules.max_automatic_substitutions
        )
        changed = (
            rules.preset_name != preset_name
            or rules.participant_count != participant_count
            or rules.total_credits != total_credits
            or rules.min_fixtures_per_round != min_fixtures
            or rules.minutes_threshold != minutes_threshold
            or rules.max_automatic_substitutions != max_automatic_substitutions
            or rules.allow_trades != payload.options.allow_trades
            or rules.allow_manual_invites != payload.options.allow_manual_invites
        )
        if not changed:
            get_metrics().incr("league_rules_updated_total", labels={"result": "noop"})
            return self._to_rules_response(rules)

        rules.preset_name = preset_name
        rules.participant_count = participant_count
        rules.roster_size = payload.roster.roster_size
        rules.goalkeepers = payload.roster.goalkeepers
        rules.defenders = payload.roster.defenders
        rules.midfielders = payload.roster.midfielders
        rules.forwards = payload.roster.forwards
        rules.total_credits = total_credits
        rules.min_fixtures_per_round = min_fixtures
        rules.minutes_threshold = minutes_threshold
        rules.max_automatic_substitutions = max_automatic_substitutions
        rules.allow_trades = payload.options.allow_trades
        rules.allow_manual_invites = payload.options.allow_manual_invites
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_RULES_UPDATED,
                correlation_id=get_correlation_id(),
            ),
        )
        self._session.commit()
        get_metrics().incr("league_rules_updated_total", labels={"result": "success"})
        return self._to_rules_response(rules)

    def delete_league(self, league_access: LeagueAccess) -> None:
        """Hard-delete a draft/configuring league; audit row survives via ON DELETE SET NULL."""
        league = self._lock_league_for_lifecycle(league_access.league.id)
        try:
            validate_league_deletable(league.state)
        except ValidationAuthError:
            get_metrics().incr("league_deleted_total", labels={"result": "not_deletable"})
            raise

        details = {
            "leagueId": str(league.id),
            "name": league.name,
            "state": league.state.value,
            "seasonYear": league.season_year,
        }
        self._session.add(
            LeagueAuditEvent(
                league_id=league.id,
                actor_id=league_access.user.id,
                action=LeagueAuditAction.LEAGUE_DELETED,
                correlation_id=get_correlation_id(),
                details=details,
            ),
        )
        self._session.flush()
        self._session.delete(league)
        self._session.commit()
        get_metrics().incr("league_deleted_total", labels={"result": "success"})
        logger.info("league_deleted", extra={"result": "success", **details})

    def _load_league_with_competitions(self, league_id: UUID) -> League:
        league = self._session.scalars(
            select(League)
            .where(League.id == league_id)
            .options(selectinload(League.competitions), selectinload(League.rules)),
        ).first()
        if league is None:
            msg = "Lega non trovata."
            raise ValidationAuthError(msg, code="league_not_found")
        return league

    def _lock_league_for_lifecycle(self, league_id: UUID) -> League:
        league = self._session.scalars(
            select(League)
            .where(League.id == league_id)
            .options(selectinload(League.competitions), selectinload(League.rules))
            .with_for_update()
        ).first()
        if league is None:
            raise ValidationAuthError("Lega non trovata.", code="league_not_found")
        return league

    def _to_lifecycle_response(self, league: League) -> LeagueLifecycleResponse:
        blockers = self._lifecycle_blockers(league)
        allowed = list(LEAGUE_TRANSITIONS[league.state])
        if league.state == LeagueState.CONFIGURING and blockers:
            allowed.remove(LeagueState.AUCTION)
        elif league.state == LeagueState.AUCTION and blockers:
            allowed.remove(LeagueState.ACTIVE)
        return LeagueLifecycleResponse(
            state=league.state,
            allowedTransitions=allowed,
            blockers=[
                LeagueLifecycleBlocker(code=blocker.code, message=blocker.message)
                for blocker in blockers
            ],
        )

    def _lifecycle_blockers(self, league: League):
        if league.state == LeagueState.CONFIGURING:
            rules = league.rules
            membership_count = self._session.scalar(
                select(func.count(LeagueMembership.id)).where(
                    LeagueMembership.league_id == league.id
                )
            )
            owner_count = self._session.scalar(
                select(func.count(LeagueMembership.id)).where(
                    LeagueMembership.league_id == league.id,
                    LeagueMembership.role == LeagueMemberRole.OWNER,
                )
            )
            return configuration_blockers(
                rules_valid=self._rules_are_valid(rules),
                competition_count=len(league.competitions),
                membership_count=membership_count or 0,
                participant_count=rules.participant_count if rules is not None else None,
                owner_count=owner_count or 0,
            )
        if league.state == LeagueState.AUCTION:
            return auction_activation_blockers(
                calendar_configured=league_has_confirmed_calendar(self._session, league.id),
                roster_blockers=activation_roster_and_credit_blockers(self._session, league),
            )
        return []

    @staticmethod
    def _rules_are_valid(rules: LeagueRules | None) -> bool:
        return bool(
            rules is not None
            and rules.preset_name == STANDARD_PRESET_NAME
            and MIN_PARTICIPANTS <= rules.participant_count <= MAX_PARTICIPANTS
            and rules.roster_size == STANDARD_ROSTER_SIZE
            and rules.goalkeepers == STANDARD_GOALKEEPERS
            and rules.defenders == STANDARD_DEFENDERS
            and rules.midfielders == STANDARD_MIDFIELDERS
            and rules.forwards == STANDARD_FORWARDS
            and rules.goalkeepers + rules.defenders + rules.midfielders + rules.forwards
            == rules.roster_size
            and rules.total_credits > 0
        )

    @staticmethod
    def _record_transition_result(
        result: str,
        before: LeagueState,
        target: LeagueState,
    ) -> None:
        labels = {"result": result, "from": before.value, "to": target.value}
        get_metrics().incr("league_state_transition_total", labels=labels)
        logger.info("league_state_transition", extra=labels)

    @staticmethod
    def _to_competition_summary(competition: Competition) -> CompetitionSummaryResponse:
        return CompetitionSummaryResponse(
            id=str(competition.id),
            providerId=competition.provider_id,
            name=competition.name,
            country=competition.country,
        )

    def _to_league_detail(self, league: League, *, viewer_role: str | None) -> LeagueDetailResponse:
        competitions = sorted(league.competitions, key=lambda row: row.name)
        return LeagueDetailResponse(
            id=str(league.id),
            name=league.name,
            seasonYear=league.season_year,
            state=league.state.value,
            viewerRole=viewer_role,
            competitions=[self._to_competition_summary(row) for row in competitions],
            rules=self._to_rules_response(league.rules) if league.rules is not None else None,
        )

    @staticmethod
    def _resolve_rules_for_league(league: League) -> LeagueRules:
        if league.rules is None:
            msg = "Regolamento lega non configurato."
            raise ValidationAuthError(msg, code="league_rules_not_found")
        return league.rules

    @staticmethod
    def _to_rules_response(rules: LeagueRules) -> LeagueRulesResponse:
        return LeagueRulesResponse(
            presetName=rules.preset_name,
            participantCount=rules.participant_count,
            participantMin=MIN_PARTICIPANTS,
            participantMax=MAX_PARTICIPANTS,
            roster=LeagueRosterConfig(
                rosterSize=rules.roster_size,
                goalkeepers=rules.goalkeepers,
                defenders=rules.defenders,
                midfielders=rules.midfielders,
                forwards=rules.forwards,
            ),
            totalCredits=rules.total_credits,
            minFixturesPerRound=rules.min_fixtures_per_round,
            minutesThreshold=rules.minutes_threshold,
            maxAutomaticSubstitutions=rules.max_automatic_substitutions,
            options=LeagueRulesOptions(
                allowTrades=rules.allow_trades,
                allowManualInvites=rules.allow_manual_invites,
            ),
        )
