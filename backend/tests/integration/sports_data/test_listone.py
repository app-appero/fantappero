"""Integration tests for official listone generation and overrides (EP04-04)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from auth.models.user import User
from database.enums import FantasyRole, LeagueMemberRole, LeagueState, PlatformRole, UserType
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from observability.metrics import get_metrics, reset_metrics
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.listone.generate import (
    LISTONE_GENERATE_ENTITIES_TOTAL,
    generate_official_listone,
)
from sports_data.listone.mapping import MAPPING_VERSION
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.listone.overrides import create_override, effective_role_for_athlete
from sports_data.listone.validators import compute_override_effective_from_round
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete, SquadMembership, Transfer
from sports_data.roster.sync import SquadBatch, sync_roster

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"


@pytest.fixture(autouse=True)
def clean_listone_tables(session: Session) -> None:
    session.execute(delete(LeagueRoleOverride))
    session.execute(delete(RoleAssignment))
    session.execute(delete(SquadMembership))
    session.execute(delete(Transfer))
    session.execute(delete(Athlete))
    session.commit()


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def _seed_roster(session: Session) -> None:
    leagues = parse_envelope(_load("reference/leagues.json"), endpoint="/leagues", http_status=200)
    teams = parse_envelope(_load("reference/teams.json"), endpoint="/teams", http_status=200)
    sync_catalog(
        session,
        leagues_envelope=leagues,
        teams_batches=[TeamsBatch(envelope=teams, competition_provider_id=39, season_year=2026)],
    )
    squads_wolves = parse_envelope(
        _load("reference/players_squads_wolves.json"),
        endpoint="/players/squads",
        http_status=200,
    )
    sync_roster(
        session,
        squad_batches=[
            SquadBatch(
                envelope=squads_wolves,
                club_provider_id=39,
                competition_provider_id=39,
                season_year=2026,
            )
        ],
        players_batches=[],
        transfers_envelopes=[],
    )
    session.commit()


def test_listone_generate_idempotent_and_maps_roles(session: Session) -> None:
    reset_metrics()
    _seed_roster(session)

    first = generate_official_listone(session, season_year=2026)
    session.commit()
    assert first.counters.created == 5
    assert first.counters.skipped_unmapped == 0
    assert first.mapping_version == MAPPING_VERSION

    count = session.execute(select(func.count()).select_from(RoleAssignment)).scalar_one()
    assert count == 5

    jimenez = session.execute(select(Athlete).where(Athlete.provider_id == 2887)).scalar_one()
    assignment = session.execute(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id == jimenez.id,
            RoleAssignment.season_year == 2026,
        )
    ).scalar_one()
    assert assignment.role == FantasyRole.A
    assignment_id = assignment.id

    second = generate_official_listone(session, season_year=2026)
    session.commit()
    assert second.counters.unchanged == 5
    assert second.counters.created == 0

    again = session.execute(
        select(RoleAssignment).where(RoleAssignment.athlete_id == jimenez.id)
    ).scalar_one()
    assert again.id == assignment_id

    created_metric = get_metrics().get_counter(
        LISTONE_GENERATE_ENTITIES_TOTAL,
        labels={"provider": "api-football-v3", "result": "created"},
    )
    unchanged_metric = get_metrics().get_counter(
        LISTONE_GENERATE_ENTITIES_TOTAL,
        labels={"provider": "api-football-v3", "result": "unchanged"},
    )
    assert created_metric == 5
    assert unchanged_metric == 5


def test_league_override_pre_auction_immediate_post_start_deferred(session: Session) -> None:
    _seed_roster(session)
    generate_official_listone(session, season_year=2026)
    session.commit()

    athlete = session.execute(select(Athlete).where(Athlete.provider_id == 2676)).scalar_one()
    official = session.execute(
        select(RoleAssignment).where(RoleAssignment.athlete_id == athlete.id)
    ).scalar_one()
    assert official.role == FantasyRole.C

    user = User(
        email=f"listone-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        user_type=UserType.HUMAN,
    )
    session.add(user)
    session.flush()

    league = League(name="Lega Listone", season_year=2026, state=LeagueState.AUCTION)
    session.add(league)
    session.flush()
    session.add(
        LeagueMembership(
            league_id=league.id,
            user_id=user.id,
            role=LeagueMemberRole.OWNER,
        )
    )
    session.flush()

    effective_from = compute_override_effective_from_round(
        league_state=league.state,
        current_round=None,
    )
    assert effective_from is None
    override = create_override(
        session,
        league_id=league.id,
        athlete_id=athlete.id,
        role=FantasyRole.A,
        effective_from_round=effective_from,
        actor_id=user.id,
        reason="Override pre-asta",
    )
    session.commit()
    assert (
        effective_role_for_athlete(
            official_role=official.role,
            override=override,
            current_round=0,
        )
        == FantasyRole.A
    )

    league.state = LeagueState.ACTIVE
    session.flush()
    deferred = compute_override_effective_from_round(
        league_state=league.state,
        current_round=1,
    )
    assert deferred == 2
    override2 = create_override(
        session,
        league_id=league.id,
        athlete_id=athlete.id,
        role=FantasyRole.D,
        effective_from_round=deferred,
        actor_id=user.id,
        reason="Cambio post-avvio",
    )
    session.commit()

    assert (
        effective_role_for_athlete(
            official_role=official.role,
            override=override2,
            current_round=1,
        )
        == FantasyRole.C
    )
    assert (
        effective_role_for_athlete(
            official_role=official.role,
            override=override2,
            current_round=2,
        )
        == FantasyRole.D
    )

    active = session.execute(
        select(LeagueRoleOverride).where(
            LeagueRoleOverride.league_id == league.id,
            LeagueRoleOverride.athlete_id == athlete.id,
            LeagueRoleOverride.superseded_at.is_(None),
        )
    ).scalar_one()
    assert active.id == override2.id
    superseded = session.execute(
        select(func.count())
        .select_from(LeagueRoleOverride)
        .where(
            LeagueRoleOverride.league_id == league.id,
            LeagueRoleOverride.superseded_at.is_not(None),
        )
    ).scalar_one()
    assert superseded == 1
