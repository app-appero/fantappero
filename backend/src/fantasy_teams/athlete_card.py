"""Scheda calciatore: dati già sincronizzati dal provider e rosa della lega corrente."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from authorization.context import LeagueAccess
from fantasy_teams.models import FantasyRosterSlot
from fantasy_teams.schemas import (
    AthleteCardAssignmentResponse,
    AthleteCardResponse,
    AthleteCardSeasonResponse,
    AthleteCardTransferResponse,
)
from sports_data.catalog.models import Club
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


def _club_name(club: Club | None) -> str:
    if club is None or not club.name:
        return "Club sconosciuto"
    return club.name
