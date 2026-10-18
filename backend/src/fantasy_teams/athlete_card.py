"""Scheda calciatore: dati già sincronizzati dal provider e rosa della lega corrente."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from fantasy_teams.models import FantasyRosterSlot
from fantasy_teams.schemas import (
    AthleteCardAssignmentResponse,
    AthleteCardLiveResponse,
    AthleteCardSeasonStatsResponse,
    AthleteCardResponse,
    AthleteCardSeasonResponse,
    AthleteCardTransferResponse,
)
from fantasy_ratings.models import PlayerMatchRating
from fantasy_turns.readiness import FINISHED_FIXTURE_STATUSES, LIVE_FIXTURE_STATUSES
from sports_data.catalog.models import Club
from sports_data.fixtures.models import Fixture, PlayerMatchStat
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.roster.models import Athlete, SquadMembership, Transfer


def get_athlete_card(
    session: Session,
    league_access: LeagueAccess,
    athlete_id: UUID,
) -> AthleteCardResponse:
    athlete = session.get(Athlete, athlete_id)
    if athlete is None:
        raise ValidationAuthError("Calciatore non trovato.", code="athlete_not_found")

    memberships = list(
        session.scalars(
            select(SquadMembership)
            .where(SquadMembership.athlete_id == athlete.id)
            .options(
                selectinload(SquadMembership.club),
                selectinload(SquadMembership.sport_season),
            )
        ).all()
    )
    memberships.sort(
        key=lambda row: (
            row.sport_season.year if row.sport_season is not None else 0,
            row.is_active,
        ),
        reverse=True,
    )

    transfers = session.scalars(
        select(Transfer)
        .where(Transfer.athlete_id == athlete.id)
        .options(
            selectinload(Transfer.from_club),
            selectinload(Transfer.to_club),
        )
        .order_by(Transfer.transfer_date.desc(), Transfer.id.desc())
    ).all()

    season_year = league_access.league.season_year
    role_row = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id == athlete.id,
            RoleAssignment.season_year == season_year,
        )
    )
    if role_row is None:
        role_row = session.scalar(
            select(RoleAssignment)
            .where(RoleAssignment.athlete_id == athlete.id)
            .order_by(RoleAssignment.season_year.desc())
        )

    override = session.scalar(
        select(LeagueRoleOverride).where(
            LeagueRoleOverride.league_id == league_access.league.id,
            LeagueRoleOverride.athlete_id == athlete.id,
            LeagueRoleOverride.superseded_at.is_(None),
        )
    )

    slot = session.scalar(
        select(FantasyRosterSlot)
        .where(
            FantasyRosterSlot.league_id == league_access.league.id,
            FantasyRosterSlot.athlete_id == athlete.id,
        )
        .options(selectinload(FantasyRosterSlot.fantasy_team))
    )

    current = next(
        (row for row in memberships if row.is_active),
        memberships[0] if memberships else None,
    )
    official_role = role_row.role.value if role_row is not None else None
    effective_role = override.role.value if override is not None else official_role
    position_raw = (
        role_row.provider_position_raw
        if role_row is not None and role_row.provider_position_raw
        else (current.provider_position_raw if current is not None else None)
    )

    season_stats, live = _season_stats(
        session,
        athlete.id,
        current.sport_season_id if current is not None else None,
        league_access.league.id,
    )

    return AthleteCardResponse(
        athleteId=str(athlete.id),
        providerId=athlete.provider_id,
        canonicalName=athlete.canonical_name,
        firstName=athlete.first_name,
        lastName=athlete.last_name,
        nationality=athlete.nationality,
        birthDate=athlete.birth_date.isoformat() if athlete.birth_date else None,
        age=athlete.age,
        height=athlete.height,
        weight=athlete.weight,
        injured=athlete.injured,
        photoUrl=athlete.photo_url,
        clubName=_club_name(current.club) if current is not None else None,
        shirtNumber=current.shirt_number if current is not None else None,
        role=official_role,
        effectiveRole=effective_role,
        providerPositionRaw=position_raw,
        assignment=(
            AthleteCardAssignmentResponse(
                fantasyTeamId=str(slot.fantasy_team_id),
                teamName=slot.fantasy_team.name,
                slotIndex=slot.slot_index,
                purchaseCredits=slot.purchase_credits,
            )
            if slot is not None and slot.fantasy_team is not None
            else None
        ),
        seasons=[
            AthleteCardSeasonResponse(
                clubName=_club_name(row.club),
                seasonYear=row.sport_season.year if row.sport_season is not None else 0,
                shirtNumber=row.shirt_number,
                positionRaw=row.provider_position_raw,
                isActive=row.is_active,
            )
            for row in memberships
        ],
        seasonStats=season_stats,
        live=live,
        transfers=[
            AthleteCardTransferResponse(
                transferDate=row.transfer_date.isoformat(),
                fromClubName=_club_name(row.from_club) if row.from_club is not None else None,
                toClubName=_club_name(row.to_club) if row.to_club is not None else None,
                transferType=row.transfer_type,
            )
            for row in transfers
        ],
    )


def _int(value: object) -> int:
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return 0


def _rating(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _season_stats(
    session: Session,
    athlete_id: UUID,
    season_id: UUID | None,
    league_id: UUID,
) -> tuple[AthleteCardSeasonStatsResponse | None, AthleteCardLiveResponse | None]:
    """Gol, assist, media voto e voto live dal campionato corrente del calciatore."""
    if season_id is None:
        return None, None
    rows = session.execute(
        select(PlayerMatchStat, Fixture)
        .join(Fixture, Fixture.id == PlayerMatchStat.fixture_id)
        .where(
            PlayerMatchStat.athlete_id == athlete_id,
            Fixture.sport_season_id == season_id,
        )
        .order_by(Fixture.kickoff_at.desc())
    ).all()
    counted = [
        (stat, fixture)
        for stat, fixture in rows
        if (fixture.status_short or "").upper() in FINISHED_FIXTURE_STATUSES | LIVE_FIXTURE_STATUSES
    ]
    if not counted:
        return None, None
    fixture_ids = [fixture.id for _, fixture in counted]
    fantasy_by_fixture = {
        row.fixture_id: row.fantasy_score
        for row in session.scalars(
            select(PlayerMatchRating).where(
                PlayerMatchRating.athlete_id == athlete_id,
                PlayerMatchRating.fixture_id.in_(fixture_ids),
                or_(
                    PlayerMatchRating.league_id == league_id,
                    PlayerMatchRating.league_id.is_(None),
                ),
                PlayerMatchRating.fantasy_score.is_not(None),
            )
        ).all()
    }
    matches = goals = assists = 0
    ratings: list[float] = []
    live: AthleteCardLiveResponse | None = None
    for stat, fixture in counted:
        statistics = stat.stats_json if isinstance(stat.stats_json, dict) else {}
        goal_block = statistics.get("goals") if isinstance(statistics.get("goals"), dict) else {}
        status = (fixture.status_short or "").upper()
        if status in LIVE_FIXTURE_STATUSES:
            if live is None and (stat.minutes or 0) > 0:
                fantasy = fantasy_by_fixture.get(fixture.id)
                live = AthleteCardLiveResponse(
                    score=fantasy if fantasy is not None else _rating(stat.provider_rating),
                    isFantasy=fantasy is not None,
                )
            continue
        if (stat.minutes or 0) <= 0:
            continue
        matches += 1
        goals += _int(goal_block.get("total"))
        assists += _int(goal_block.get("assists"))
        rating = _rating(stat.provider_rating)
        if rating is not None:
            ratings.append(rating)
    fantasy_scores = [v for k, v in fantasy_by_fixture.items() if v is not None]
    return (
        AthleteCardSeasonStatsResponse(
            matches=matches,
            goals=goals,
            assists=assists,
            averageRating=round(sum(ratings) / len(ratings), 2) if ratings else None,
            fantasyAverage=round(sum(fantasy_scores) / len(fantasy_scores), 2) if fantasy_scores else None,
        ),
        live,
    )


def _club_name(club: Club | None) -> str:
    if club is None or not club.name:
        return "Club sconosciuto"
    return club.name
