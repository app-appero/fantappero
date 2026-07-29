"""League creation and updates with authorization preconditions (EP03-01)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from authorization.service import AuthorizationService
from database.enums import LeagueAuditAction, LeagueMemberRole, LeagueState
from database.models.accounts import User
from database.models.competitions import Competition
from database.models.league_audit import LeagueAuditEvent
from database.models.leagues import League, LeagueMembership
from leagues.errors import LeagueValidationError
from leagues.schemas import (
    CompetitionResponse,
    CreateLeagueRequest,
    LeagueCompetitionSummary,
    LeagueResponse,
)
from leagues.validation import (
    LeagueValidationRuleError,
    rule_error_to_league_error,
    validate_competition_ids,
    validate_league_name,
    validate_season_year,
)


class LeagueService:
    """Domain service for league resources."""

    def __init__(self, db: Session, authorization: AuthorizationService) -> None:
        self._db = db
        self._authorization = authorization

    def list_competitions(self) -> list[CompetitionResponse]:
        rows = self._db.scalars(select(Competition).order_by(Competition.name)).all()
        return [CompetitionResponse.model_validate(row) for row in rows]

    def create_league(
        self,
        *,
        owner: User,
        body: CreateLeagueRequest,
        correlation_id: str | None = None,
    ) -> LeagueResponse:
        self._authorization.require_league_create(actor=owner)

        allowed = self._load_competition_ids()
        try:
            name = validate_league_name(body.name)
            season_year = validate_season_year(body.season_year)
            competition_ids = validate_competition_ids(
                body.competition_ids,
                allowed_ids=allowed,
            )
        except LeagueValidationRuleError as exc:
            raise rule_error_to_league_error(exc) from exc

        competitions = self._load_competitions(competition_ids)
        if len(competitions) != len(competition_ids):
            raise LeagueValidationError("One or more competitions are not available.")

        league = League(
            name=name,
            season_year=season_year,
            state=LeagueState.DRAFT,
        )
        league.competitions = competitions
        self._db.add(league)
        self._db.flush()

        membership = LeagueMembership(
            league_id=league.id,
            user_id=owner.id,
            role=LeagueMemberRole.OWNER,
        )
        self._db.add(membership)
        self._record_audit(
            league_id=league.id,
            actor_id=owner.id,
            action=LeagueAuditAction.LEAGUE_CREATED,
            correlation_id=correlation_id,
        )
        return self._to_response(league, membership.role.value)

    def get_league(self, *, actor: User, league_id: uuid.UUID) -> LeagueResponse:
        league, membership = self._authorization.require_league_read(
            actor=actor,
            league_id=league_id,
        )
        loaded = self._load_league_with_competitions(league.id)
        role = membership.role.value if membership is not None else None
        return self._to_response(loaded, role)

    def update_league(self, *, actor: User, league_id: uuid.UUID, name: str) -> LeagueResponse:
        league, membership = self._authorization.require_league_update(
            actor=actor,
            league_id=league_id,
        )
        try:
            league.name = validate_league_name(name)
        except LeagueValidationRuleError as exc:
            raise rule_error_to_league_error(exc) from exc

        self._db.add(league)
        loaded = self._load_league_with_competitions(league.id)
        role = membership.role.value if membership is not None else None
        return self._to_response(loaded, role)

    def _load_competition_ids(self) -> set[uuid.UUID]:
        rows = self._db.scalars(select(Competition.id)).all()
        return set(rows)

    def _load_competitions(self, competition_ids: list[uuid.UUID]) -> list[Competition]:
        rows = self._db.scalars(
            select(Competition).where(Competition.id.in_(competition_ids))
        ).all()
        by_id = {row.id: row for row in rows}
        return [by_id[item] for item in competition_ids]

    def _load_league_with_competitions(self, league_id: uuid.UUID) -> League:
        league = self._db.scalar(
            select(League)
            .options(joinedload(League.competitions))
            .where(League.id == league_id)
        )
        if league is None:
            raise LeagueValidationError("League not found.")
        return league

    def _record_audit(
        self,
        *,
        league_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: LeagueAuditAction,
        correlation_id: str | None,
    ) -> None:
        event = LeagueAuditEvent(
            league_id=league_id,
            actor_id=actor_id,
            action=action,
            correlation_id=correlation_id,
        )
        self._db.add(event)

    @staticmethod
    def _to_response(league: League, role: str | None) -> LeagueResponse:
        competitions = [
            LeagueCompetitionSummary(
                id=item.id,
                provider_id=item.provider_id,
                name=item.name,
                country=item.country,
            )
            for item in sorted(league.competitions, key=lambda row: row.name)
        ]
        return LeagueResponse(
            id=league.id,
            name=league.name,
            season_year=league.season_year,
            state=league.state.value,
            role=role,
            competitions=competitions,
        )
