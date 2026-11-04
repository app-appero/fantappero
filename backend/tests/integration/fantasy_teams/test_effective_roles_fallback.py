# ruff: noqa: F811
"""Ruolo effettivo di un calciatore in rosa anche senza assegnazione del listone (formazione)."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.integration.fantasy_teams.test_athlete_card import (  # noqa: F401
    _register_and_login,
    competition_ids,
    db_session,
)

from database.enums import FantasyRole
from fantasy_teams.composition_service import resolve_effective_athlete_roles
from sports_data.catalog.models import Club, SportSeason
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete, SquadMembership


def test_role_falls_back_to_squad_position_and_older_assignment(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "roles.fallback@example.com")
    created = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Lega Ruoli", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201
    league_id = UUID(created.json()["id"])

    club = Club(provider_id=990501, name="Monaco")
    db_session.add(club)
    db_session.flush()
    season = SportSeason(competition_id=UUID(competition_ids[0]), year=2026, is_current=False)
    db_session.add(season)
    db_session.flush()

    keeper = Athlete(provider_id=990502, canonical_name="Portiere Nuovo")
    mid = Athlete(provider_id=990503, canonical_name="Centrocampista Nuovo")
    old = Athlete(provider_id=990504, canonical_name="Ruolo Vecchio")
    unknown = Athlete(provider_id=990505, canonical_name="Senza Dati")
    db_session.add_all([keeper, mid, old, unknown])
    db_session.flush()
    for athlete, position in ((keeper, "Goalkeeper"), (mid, "Midfielder")):
        db_session.add(
            SquadMembership(
                athlete_id=athlete.id,
                club_id=club.id,
                sport_season_id=season.id,
                provider_position_raw=position,
                is_active=True,
                source="squads",
            )
        )
    db_session.add(
        RoleAssignment(
            athlete_id=old.id,
            season_year=2025,
            role=FantasyRole.D,
            mapping_version="v1.0.0",
            provider_position_raw="Defender",
        )
    )
    db_session.commit()

    roles = resolve_effective_athlete_roles(
        db_session,
        league_id=league_id,
        athlete_ids=[keeper.id, mid.id, old.id, unknown.id],
        season_year=2026,
    )
    assert roles[keeper.id].role == FantasyRole.P
    assert roles[mid.id].role == FantasyRole.C
    assert roles[old.id].role == FantasyRole.D
    assert unknown.id not in roles
