"""Integration tests for lineup modules, validation and cutoff (EP06-02)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

import auth.dependencies as auth_dependencies
from database.enums import (
    FantasyRole,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueAuditAction,
    RosterCompositionStatus,
)
from database.session import create_session_factory
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_lineups.rules import remaining_roster_for_bench
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from leagues.models.league_audit_event import LeagueAuditEvent
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200
    return login.json()["accessToken"], UUID(login.json()["user"]["id"])


@pytest.fixture
def db_session(db_url: str) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def competition_ids(db_session: Session) -> list[str]:
    rows = db_session.scalars(select(Competition).order_by(Competition.name.asc())).all()
    assert len(rows) >= 3
    return [str(row.id) for row in rows[:3]]


def _create_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_roster_athletes(db_session: Session, *, id_offset: int) -> dict[str, list[Athlete]]:
    grouped: dict[str, list[Athlete]] = {"P": [], "D": [], "C": [], "A": []}
    counts = {FantasyRole.P: 3, FantasyRole.D: 11, FantasyRole.C: 11, FantasyRole.A: 10}
    provider_id = id_offset
    for role, count in counts.items():
        for index in range(count):
            athlete = Athlete(
                provider_id=provider_id,
                canonical_name=f"{role.value} {index + 1}",
            )
            provider_id += 1
            db_session.add(athlete)
            db_session.flush()
            db_session.add(
                RoleAssignment(
                    athlete_id=athlete.id,
                    season_year=2026,
                    role=role,
                    mapping_version="v1.0.0",
                    provider_position_raw=role.value,
                )
            )
            grouped[role.value].append(athlete)
    db_session.commit()
    return grouped


def _fill_validated_roster(
    db_session: Session,
    league_id: str,
    grouped: dict[str, list[Athlete]],
) -> list[Athlete]:
    team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).one()
    slots = db_session.scalars(
        select(FantasyRosterSlot)
        .where(FantasyRosterSlot.fantasy_team_id == team.id)
        .order_by(FantasyRosterSlot.slot_index.asc())
    ).all()
    ordered = [*grouped["P"], *grouped["D"], *grouped["C"], *grouped["A"]]
    assert len(slots) >= len(ordered)
    for slot, athlete in zip(slots, ordered, strict=False):
        slot.athlete_id = athlete.id
        slot.purchase_credits = 1
    team.composition_status = RosterCompositionStatus.VALIDATED
    team.validated_at = datetime.now(UTC)
    db_session.commit()
    return ordered


def _create_open_round(
    db_session: Session,
    league_id: str,
    *,
    cutoff: datetime,
    extra_kickoff: datetime | None = None,
    status: FantasyTurnStatus = FantasyTurnStatus.OPEN,
    id_offset: int,
    competition_ids: list[str],
    number: int = 1,
) -> tuple[FantasyRound, list[Club]]:
    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=number,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=cutoff - timedelta(days=1),
        window_end_at=cutoff + timedelta(days=3),
        cutoff_at=cutoff,
        status=status,
        generated_at=now,
        opens_at=now if status == FantasyTurnStatus.OPEN else None,
    )
    db_session.add(fantasy_round)
    db_session.flush()

    kickoffs = [cutoff]
    if extra_kickoff is not None:
        kickoffs.append(extra_kickoff)
    clubs: list[Club] = []
    for i in range(len(kickoffs) * 2):
        club = Club(provider_id=id_offset + i, name=f"Club LU {id_offset}-{i}")
        db_session.add(club)
        clubs.append(club)
    db_session.flush()

    competition_id = UUID(competition_ids[0])
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition_id,
            SportSeason.year == 2026,
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()

    for i, kickoff in enumerate(kickoffs):
        fixture = Fixture(
            provider_id=id_offset + 50_000 + i,
            sport_season_id=season.id,
            home_club_id=clubs[i * 2].id,
            away_club_id=clubs[i * 2 + 1].id,
            kickoff_at=kickoff,
            status_short="NS",
        )
        db_session.add(fixture)
        db_session.flush()
        db_session.add(
            FantasyRoundFixture(
                round_id=fantasy_round.id,
                league_id=UUID(league_id),
                fixture_id=fixture.id,
                observed_kickoff_at=kickoff,
            )
        )
    db_session.commit()
    db_session.refresh(fantasy_round)
    return fantasy_round, clubs


def _lineup_payload(athletes: list[Athlete], module: str = "4-3-3") -> dict:
    by_role: dict[str, list[str]] = {"P": [], "D": [], "C": [], "A": []}
    for athlete in athletes:
        prefix = athlete.canonical_name[0]
        by_role[prefix].append(str(athlete.id))
    if module == "4-3-3":
        starters = [
            *by_role["P"][:1],
            *by_role["D"][:4],
            *by_role["C"][:3],
            *by_role["A"][:3],
        ]
    else:
        starters = [
            *by_role["P"][:1],
            *by_role["D"][:3],
            *by_role["C"][:5],
            *by_role["A"][:2],
        ]
    roster_ids = [str(athlete.id) for athlete in athletes]
    bench = remaining_roster_for_bench(roster_ids, starters)
    return {
        "module": module,
        "starterAthleteIds": starters,
        "benchAthleteIds": bench,
    }


def _count_request_queries(call) -> tuple[object, int]:
    engine = auth_dependencies._engine
    assert engine is not None
    count = 0

    def _before_cursor_execute(*_args: object) -> None:
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        response = call()
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)
    return response, count


def test_full_roster_and_lineup_query_counts_are_bounded(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Guard against reintroducing per-player listone/override queries."""
    token, _ = _register_and_login(client, "lineup.query-budget@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Query Budget")
    grouped = _seed_roster_athletes(db_session, id_offset=2_390_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        id_offset=2_395_000,
        competition_ids=competition_ids,
    )
    headers = {"Authorization": f"Bearer {token}"}
    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers=headers,
        json=_lineup_payload(athletes),
    )
    assert saved.status_code == 200

    roster, roster_queries = _count_request_queries(
        lambda: client.get(f"/leagues/{league_id}/rosa", headers=headers)
    )
    lineup, lineup_queries = _count_request_queries(
        lambda: client.get(
            f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
            headers=headers,
        )
    )

    assert roster.status_code == 200
    assert roster.json()["filledSlots"] == 35
    assert roster_queries <= 25
    assert lineup.status_code == 200
    assert len(lineup.json()["roster"]) == 35
    assert lineup_queries <= 35


def test_roster_exposes_athlete_photo_url_when_available(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """La foto del calciatore (Athlete.photo_url) arriva fino al roster della formazione."""
    token, _ = _register_and_login(client, "lineup.photo@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Foto Calciatori")
    grouped = _seed_roster_athletes(db_session, id_offset=2_420_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)

    photographed = grouped["P"][0]
    photographed.photo_url = "https://cdn.example.com/athletes/photo.jpg"
    db_session.commit()

    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        id_offset=2_425_000,
        competition_ids=competition_ids,
    )
    headers = {"Authorization": f"Bearer {token}"}
    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers=headers,
        json=_lineup_payload(athletes),
    )
    assert saved.status_code == 200

    context = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers=headers,
    )
    assert context.status_code == 200
    roster_by_id = {row["athleteId"]: row for row in context.json()["roster"]}
    assert roster_by_id[str(photographed.id)]["photoUrl"] == "https://cdn.example.com/athletes/photo.jpg"
    other = grouped["P"][1]
    assert roster_by_id[str(other.id)]["photoUrl"] is None


def test_save_valid_module_and_reject_incompatible(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lineup.ok@example.com")
    outsider, _ = _register_and_login(client, "lineup.out@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Formazione")
    rosa = client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    assert rosa.status_code == 200

    grouped = _seed_roster_athletes(db_session, id_offset=2_400_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)
    cutoff = datetime.now(UTC) + timedelta(hours=4)
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=cutoff,
        extra_kickoff=cutoff,
        id_offset=2_410_000,
        competition_ids=competition_ids,
    )

    forbidden = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {outsider}"},
    )
    assert forbidden.status_code == 403

    empty = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert empty.status_code == 200
    body = empty.json()
    assert body["lineup"] is None
    assert body["draft"] is None
    assert body["previousLineup"] is None
    assert body["copyAvailable"] is False
    assert body["modificationAllowed"] is True
    assert body["maxAutomaticSubstitutions"] == 5
    assert body["maxTacticalMoves"] == 3
    assert body["tacticalMovesUsed"] == 0
    assert body["tacticalMovesRemaining"] == 3
    assert len(body["modules"]) == 7

    payload_433 = _lineup_payload(athletes, "4-3-3")
    invalid = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={**payload_433, "module": "3-5-2"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "module_role_mismatch"
    assert "3-5-2" in invalid.json()["message"]

    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload_433,
    )
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["lineup"]["module"] == "4-3-3"
    assert saved_body["lineup"]["revision"] == 1
    assert len(saved_body["lineup"]["starters"]) == 11
    assert len(saved_body["lineup"]["bench"]) == 24
    assert saved_body["issues"] == []

    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_SAVED,
        )
    ).all()
    assert len(audit) == 1


def _set_athlete_club(
    db_session: Session,
    athlete: Athlete,
    club: Club,
    *,
    season_year: int = 2026,
) -> None:
    assignment = db_session.scalars(
        select(RoleAssignment).where(
            RoleAssignment.athlete_id == athlete.id,
            RoleAssignment.season_year == season_year,
        )
    ).one()
    assignment.club_id = club.id
    db_session.commit()


def _round_fixtures(db_session: Session, round_id: UUID) -> list[Fixture]:
    links = db_session.scalars(
        select(FantasyRoundFixture)
        .where(FantasyRoundFixture.round_id == round_id)
        .order_by(FantasyRoundFixture.created_at.asc())
    ).all()
    fixtures: list[Fixture] = []
    for link in links:
        fixture = db_session.get(Fixture, link.fixture_id)
        assert fixture is not None
        fixtures.append(fixture)
    return fixtures


def test_server_rejects_scheduled_turn_unmapped_players_stay_editable(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lineup.late@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Cutoff")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=2_500_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)

    rome = ZoneInfo("Europe/Rome")
    past_local = datetime.now(rome) - timedelta(hours=1)
    past_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=past_local,
        extra_kickoff=past_local,
        id_offset=2_510_000,
        competition_ids=competition_ids,
    )
    # No club mapping → no per-player kickoff → still editable after first cutoff.
    late = client.put(
        f"/leagues/{league_id}/turni/{past_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=_lineup_payload(athletes),
    )
    assert late.status_code == 200
    assert late.json()["lineup"]["revision"] == 1

    scheduled = FantasyRound(
        league_id=UUID(league_id),
        number=2,
        kind=FantasyTurnKind.MIDWEEK,
        window_start_at=datetime.now(UTC) + timedelta(days=2),
        window_end_at=datetime.now(UTC) + timedelta(days=5),
        cutoff_at=datetime.now(UTC) + timedelta(days=3),
        status=FantasyTurnStatus.SCHEDULED,
        generated_at=datetime.now(UTC),
    )
    db_session.add(scheduled)
    db_session.commit()
    db_session.refresh(scheduled)
    too_early = client.put(
        f"/leagues/{league_id}/turni/{scheduled.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=_lineup_payload(athletes),
    )
    assert too_early.status_code == 400
    assert too_early.json()["code"] == "turn_not_open"


def test_progressive_kickoff_lock_future_players_remain_editable(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lineup.lock@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Lock Progressivo")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=2_700_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)

    rome = ZoneInfo("Europe/Rome")
    first_kickoff = datetime.now(UTC) + timedelta(hours=2)
    later_kickoff = datetime.now(rome) + timedelta(hours=5)
    fantasy_round, clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=first_kickoff,
        extra_kickoff=later_kickoff,
        id_offset=2_710_000,
        competition_ids=competition_ids,
    )
    assert len(clubs) >= 4
    locked_gk = grouped["P"][0]
    future_mid = grouped["C"][0]
    bench_mid = grouped["C"][3]
    _set_athlete_club(db_session, locked_gk, clubs[0])
    _set_athlete_club(db_session, future_mid, clubs[2])
    _set_athlete_club(db_session, bench_mid, clubs[2])

    payload = _lineup_payload(athletes, "4-3-3")
    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert saved.status_code == 200

    fixtures = _round_fixtures(db_session, fantasy_round.id)
    assert len(fixtures) == 2
    first_fixture = next(item for item in fixtures if item.home_club_id == clubs[0].id)
    later_fixture = next(item for item in fixtures if item.home_club_id == clubs[2].id)
    first_fixture.kickoff_at = datetime.now(UTC) - timedelta(minutes=5)
    first_fixture.status_short = "1H"
    db_session.commit()

    context = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert context.status_code == 200
    body = context.json()
    assert body["modificationAllowed"] is True
    assert "serverNow" in body
    roster_by_id = {row["athleteId"]: row for row in body["roster"]}
    assert roster_by_id[str(locked_gk.id)]["locked"] is True
    assert roster_by_id[str(future_mid.id)]["locked"] is False

    moved_locked = list(payload["starterAthleteIds"])
    moved_locked[0] = str(grouped["P"][1].id)
    locked_bench = [item for item in payload["benchAthleteIds"] if item != str(grouped["P"][1].id)]
    locked_bench.append(str(locked_gk.id))
    rejected = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": moved_locked,
            "benchAthleteIds": locked_bench,
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "athlete_kickoff_locked"

    swapped_starters = list(payload["starterAthleteIds"])
    c_index = swapped_starters.index(str(future_mid.id))
    swapped_starters[c_index] = str(bench_mid.id)
    swapped_bench = [item for item in payload["benchAthleteIds"] if item != str(bench_mid.id)]
    swapped_bench.append(str(future_mid.id))
    allowed = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": swapped_starters,
            "benchAthleteIds": swapped_bench,
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["lineup"]["revision"] == 2
    assert allowed.json()["tacticalMovesUsed"] == 1
    assert allowed.json()["tacticalMovesRemaining"] == 2

    # Simultaneous kickoff: the remaining future fixture locks at the same instant.
    later_fixture.kickoff_at = first_fixture.kickoff_at
    later_fixture.status_short = "NS"
    db_session.commit()
    simultaneous = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert simultaneous.status_code == 400
    assert simultaneous.json()["code"] == "athlete_kickoff_locked"


def test_ordered_bench_persists_and_locked_order_is_rejected(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lineup.bench@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Panchina")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=2_800_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)

    rome = ZoneInfo("Europe/Rome")
    first_kickoff = datetime.now(UTC) + timedelta(hours=2)
    later_kickoff = datetime.now(rome) + timedelta(hours=5)
    fantasy_round, clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=first_kickoff,
        extra_kickoff=later_kickoff,
        id_offset=2_810_000,
        competition_ids=competition_ids,
    )
    payload = _lineup_payload(athletes, "4-3-3")
    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert saved.status_code == 200
    original_ids = [row["athleteId"] for row in saved.json()["lineup"]["bench"]]
    saved_orders = [row["sortOrder"] for row in saved.json()["lineup"]["bench"]]
    assert saved_orders == list(range(len(original_ids)))
    assert len(original_ids) >= 2

    reordered = list(original_ids)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    allowed = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": payload["starterAthleteIds"],
            "benchAthleteIds": reordered,
        },
    )
    assert allowed.status_code == 200
    saved_rows = sorted(allowed.json()["lineup"]["bench"], key=lambda row: row["sortOrder"])
    saved_bench = [row["athleteId"] for row in saved_rows]
    assert saved_bench == reordered
    assert allowed.json()["maxAutomaticSubstitutions"] == 5

    locked_bench_player = grouped["P"][1]
    future_bench_player = grouped["P"][2]
    _set_athlete_club(db_session, locked_bench_player, clubs[0])
    _set_athlete_club(db_session, future_bench_player, clubs[2])
    fixtures = _round_fixtures(db_session, fantasy_round.id)
    first_fixture = next(item for item in fixtures if item.home_club_id == clubs[0].id)
    later_fixture = next(item for item in fixtures if item.home_club_id == clubs[2].id)
    first_fixture.kickoff_at = datetime.now(UTC) - timedelta(minutes=5)
    first_fixture.status_short = "1H"
    db_session.commit()

    locked_id = str(locked_bench_player.id)
    future_id = str(future_bench_player.id)
    crossed = list(reordered)
    locked_index = crossed.index(locked_id)
    future_index = crossed.index(future_id)
    crossed[locked_index], crossed[future_index] = crossed[future_index], crossed[locked_index]
    rejected = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": payload["starterAthleteIds"],
            "benchAthleteIds": crossed,
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "bench_order_locked"

    # Simultaneous kickoffs lock both remaining bench keepers together.
    later_fixture.kickoff_at = first_fixture.kickoff_at
    later_fixture.status_short = "NS"
    db_session.commit()
    simultaneous = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": payload["starterAthleteIds"],
            "benchAthleteIds": crossed,
        },
    )
    assert simultaneous.status_code == 400
    assert simultaneous.json()["code"] == "bench_order_locked"


def test_unvalidated_roster_is_rejected(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lineup.rosa@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Rosa Invalida")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    cutoff = datetime.now(UTC) + timedelta(hours=3)
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=cutoff,
        id_offset=2_610_000,
        competition_ids=competition_ids,
    )
    response = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={"module": "4-3-3", "starterAthleteIds": [], "benchAthleteIds": []},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "roster_not_validated"


def _swap_starter_with_bench(payload: dict, starter_id: str, bench_id: str) -> dict:
    starters = list(payload["starterAthleteIds"])
    bench = list(payload["benchAthleteIds"])
    starters[starters.index(starter_id)] = bench_id
    bench = [item for item in bench if item != bench_id]
    bench.append(starter_id)
    return {
        "module": payload["module"],
        "starterAthleteIds": starters,
        "benchAthleteIds": bench,
    }


def test_fourth_tactical_move_is_rejected_and_locked_players_stay_frozen(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lineup.moves@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Mosse")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=2_900_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)

    rome = ZoneInfo("Europe/Rome")
    first_kickoff = datetime.now(UTC) + timedelta(hours=2)
    later_kickoff = datetime.now(rome) + timedelta(hours=5)
    fantasy_round, clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=first_kickoff,
        extra_kickoff=later_kickoff,
        id_offset=2_910_000,
        competition_ids=competition_ids,
    )
    locked_gk = grouped["P"][0]
    starter_mid = grouped["C"][0]
    bench_mids = grouped["C"][3:7]
    _set_athlete_club(db_session, locked_gk, clubs[0])
    _set_athlete_club(db_session, starter_mid, clubs[2])
    for mid in bench_mids:
        _set_athlete_club(db_session, mid, clubs[2])

    payload = _lineup_payload(athletes, "4-3-3")
    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert saved.status_code == 200
    assert saved.json()["tacticalMovesUsed"] == 0

    fixtures = _round_fixtures(db_session, fantasy_round.id)
    first_fixture = next(item for item in fixtures if item.home_club_id == clubs[0].id)
    later_fixture = next(item for item in fixtures if item.home_club_id == clubs[2].id)
    first_fixture.kickoff_at = datetime.now(UTC) - timedelta(minutes=5)
    first_fixture.status_short = "1H"
    db_session.commit()

    moved_locked = list(payload["starterAthleteIds"])
    moved_locked[0] = str(grouped["P"][1].id)
    locked_bench = [item for item in payload["benchAthleteIds"] if item != str(grouped["P"][1].id)]
    locked_bench.append(str(locked_gk.id))
    rejected_lock = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": moved_locked,
            "benchAthleteIds": locked_bench,
        },
    )
    assert rejected_lock.status_code == 400
    assert rejected_lock.json()["code"] == "athlete_kickoff_locked"

    current = {
        "module": "4-3-3",
        "starterAthleteIds": list(payload["starterAthleteIds"]),
        "benchAthleteIds": list(payload["benchAthleteIds"]),
    }
    current_starter = str(starter_mid.id)
    for index, bench_mid in enumerate(bench_mids[:3]):
        nxt = _swap_starter_with_bench(current, current_starter, str(bench_mid.id))
        response = client.put(
            f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
            headers={"Authorization": f"Bearer {token}"},
            json=nxt,
        )
        assert response.status_code == 200
        assert response.json()["tacticalMovesUsed"] == index + 1
        assert response.json()["tacticalMovesRemaining"] == 3 - (index + 1)
        current_starter = str(bench_mid.id)
        current = nxt

    fourth = _swap_starter_with_bench(current, current_starter, str(bench_mids[3].id))
    exhausted = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=fourth,
    )
    assert exhausted.status_code == 400
    assert exhausted.json()["code"] == "tactical_moves_exhausted"

    later_fixture.kickoff_at = first_fixture.kickoff_at
    later_fixture.status_short = "NS"
    db_session.commit()
    simultaneous = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=fourth,
    )
    assert simultaneous.status_code == 400
    assert simultaneous.json()["code"] in {"tactical_moves_exhausted", "athlete_kickoff_locked"}

    context = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert context.status_code == 200
    body = context.json()
    assert body["tacticalMovesUsed"] == 3
    assert body["tacticalMovesRemaining"] == 0
    assert len(body["tacticalMoves"]) == 3
    assert body["lineup"]["revision"] == 4

    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_TACTICAL_MOVE_APPLIED,
        )
    ).all()
    assert len(audit) == 3


def test_copy_previous_lineup_revalidates_roster_and_rejects_out_of_time(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lineup.copy@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Copia")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=3_000_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)

    rome = ZoneInfo("Europe/Rome")
    cutoff = datetime.now(UTC) + timedelta(hours=6)
    round_one, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=cutoff,
        extra_kickoff=cutoff,
        id_offset=3_010_000,
        competition_ids=competition_ids,
        number=1,
    )
    payload = _lineup_payload(athletes, "4-3-3")
    saved = client.put(
        f"/leagues/{league_id}/turni/{round_one.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert saved.status_code == 200

    missing = client.post(
        f"/leagues/{league_id}/turni/{round_one.id}/formazione/copia",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing.status_code == 400
    assert missing.json()["code"] == "previous_lineup_not_found"

    later_kickoff = datetime.now(rome) + timedelta(hours=8)
    round_two, clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        extra_kickoff=later_kickoff,
        id_offset=3_020_000,
        competition_ids=competition_ids,
        number=2,
    )
    copied = client.post(
        f"/leagues/{league_id}/turni/{round_two.id}/formazione/copia",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert copied.status_code == 200
    copied_body = copied.json()
    assert copied_body["lineup"] is None
    assert copied_body["draft"] is not None
    assert copied_body["draft"]["module"] == "4-3-3"
    assert copied_body["draft"]["copySourceRoundNumber"] == 1
    assert copied_body["previousLineup"]["roundNumber"] == 1
    assert copied_body["tacticalMovesUsed"] == 0
    assert copied_body["copyAvailable"] is True

    dropped_starter = payload["starterAthleteIds"][4]
    team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).one()
    slot = db_session.scalars(
        select(FantasyRosterSlot).where(
            FantasyRosterSlot.fantasy_team_id == team.id,
            FantasyRosterSlot.athlete_id == UUID(dropped_starter),
        )
    ).one()
    replacement = Athlete(provider_id=3_030_001, canonical_name="D extra")
    db_session.add(replacement)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            athlete_id=replacement.id,
            season_year=2026,
            role=FantasyRole.D,
            mapping_version="v1.0.0",
            provider_position_raw="D",
        )
    )
    slot.athlete_id = replacement.id
    db_session.commit()

    recopied = client.post(
        f"/leagues/{league_id}/turni/{round_two.id}/formazione/copia",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recopied.status_code == 200
    recopied_body = recopied.json()
    assert any(
        issue["code"] == "copied_athlete_not_in_roster" for issue in recopied_body["copyIssues"]
    )
    assert dropped_starter not in recopied_body["draft"]["starterAthleteIds"]
    assert str(replacement.id) in recopied_body["draft"]["benchAthleteIds"]

    locked_gk = grouped["P"][0]
    _set_athlete_club(db_session, locked_gk, clubs[0])
    fixtures = _round_fixtures(db_session, round_two.id)
    first_fixture = next(item for item in fixtures if item.home_club_id == clubs[0].id)
    later_fixture = next(item for item in fixtures if item.home_club_id == clubs[2].id)
    first_fixture.kickoff_at = datetime.now(UTC) - timedelta(minutes=5)
    first_fixture.status_short = "1H"
    later_fixture.kickoff_at = first_fixture.kickoff_at
    later_fixture.status_short = "NS"
    db_session.commit()

    unavailable = client.post(
        f"/leagues/{league_id}/turni/{round_two.id}/formazione/copia",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert unavailable.status_code == 200
    unavailable_body = unavailable.json()
    assert str(locked_gk.id) not in [
        item for item in unavailable_body["draft"]["starterAthleteIds"] if item
    ]
    assert any(
        issue["code"] == "copied_athlete_unavailable" for issue in unavailable_body["copyIssues"]
    )

    confirmed = client.put(
        f"/leagues/{league_id}/turni/{round_two.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert confirmed.status_code == 400
    assert confirmed.json()["code"] in {"athlete_kickoff_locked", "athlete_not_in_roster"}

    scheduled = FantasyRound(
        league_id=UUID(league_id),
        number=3,
        kind=FantasyTurnKind.MIDWEEK,
        window_start_at=datetime.now(UTC) + timedelta(days=2),
        window_end_at=datetime.now(UTC) + timedelta(days=5),
        cutoff_at=datetime.now(UTC) + timedelta(days=3),
        status=FantasyTurnStatus.SCHEDULED,
        generated_at=datetime.now(UTC),
    )
    db_session.add(scheduled)
    db_session.commit()
    db_session.refresh(scheduled)
    too_early = client.post(
        f"/leagues/{league_id}/turni/{scheduled.id}/formazione/copia",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert too_early.status_code == 400
    assert too_early.json()["code"] == "turn_not_open"

    copy_audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_COPIED,
        )
    ).all()
    assert len(copy_audit) >= 1


def test_lineup_draft_allows_incomplete_and_rejects_out_of_time(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lineup.draft@example.com")
    outsider, _ = _register_and_login(client, "lineup.draft.out@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Bozza")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=3_100_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)
    cutoff = datetime.now(UTC) + timedelta(hours=5)
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=cutoff,
        id_offset=3_110_000,
        competition_ids=competition_ids,
    )
    payload = _lineup_payload(athletes, "4-3-3")
    incomplete = {
        "module": "4-3-3",
        "starterAthleteIds": [*payload["starterAthleteIds"][:4], "", "", "", "", "", "", ""],
        "benchAthleteIds": payload["benchAthleteIds"][:3],
    }
    forbidden = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/bozza",
        headers={"Authorization": f"Bearer {outsider}"},
        json=incomplete,
    )
    assert forbidden.status_code == 403

    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/bozza",
        headers={"Authorization": f"Bearer {token}"},
        json=incomplete,
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["lineup"] is None
    assert body["draft"]["module"] == "4-3-3"
    assert body["draft"]["starterAthleteIds"].count("") >= 7
    assert body["tacticalMovesUsed"] == 0

    duplicate = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/bozza",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": [payload["starterAthleteIds"][0], payload["starterAthleteIds"][0]],
            "benchAthleteIds": [],
        },
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["code"] == "duplicate_athlete"

    scheduled = FantasyRound(
        league_id=UUID(league_id),
        number=2,
        kind=FantasyTurnKind.MIDWEEK,
        window_start_at=datetime.now(UTC) + timedelta(days=2),
        window_end_at=datetime.now(UTC) + timedelta(days=5),
        cutoff_at=datetime.now(UTC) + timedelta(days=3),
        status=FantasyTurnStatus.SCHEDULED,
        generated_at=datetime.now(UTC),
    )
    db_session.add(scheduled)
    db_session.commit()
    db_session.refresh(scheduled)
    too_early = client.put(
        f"/leagues/{league_id}/turni/{scheduled.id}/formazione/bozza",
        headers={"Authorization": f"Bearer {token}"},
        json=incomplete,
    )
    assert too_early.status_code == 400
    assert too_early.json()["code"] == "turn_not_open"

    draft_audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_DRAFT_SAVED,
        )
    ).all()
    assert len(draft_audit) == 1


def test_postponement_after_kickoff_keeps_lock_and_tactical_moves(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, user_id = _register_and_login(client, "lineup.postpone@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Rinvio Formazione")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=3_200_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)

    first_kickoff = datetime.now(UTC) + timedelta(hours=2)
    later_kickoff = datetime.now(UTC) + timedelta(hours=5)
    fantasy_round, clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=first_kickoff,
        extra_kickoff=later_kickoff,
        id_offset=3_210_000,
        competition_ids=competition_ids,
    )
    locked_gk = grouped["P"][0]
    future_mid = grouped["C"][0]
    bench_mid = grouped["C"][3]
    _set_athlete_club(db_session, locked_gk, clubs[0])
    _set_athlete_club(db_session, future_mid, clubs[2])
    _set_athlete_club(db_session, bench_mid, clubs[2])

    payload = _lineup_payload(athletes, "4-3-3")
    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert saved.status_code == 200

    fixtures = _round_fixtures(db_session, fantasy_round.id)
    first_fixture = next(item for item in fixtures if item.home_club_id == clubs[0].id)
    first_fixture.kickoff_at = datetime.now(UTC) - timedelta(minutes=5)
    first_fixture.status_short = "NS"
    db_session.commit()

    swapped_starters = list(payload["starterAthleteIds"])
    c_index = swapped_starters.index(str(future_mid.id))
    swapped_starters[c_index] = str(bench_mid.id)
    swapped_bench = [item for item in payload["benchAthleteIds"] if item != str(bench_mid.id)]
    swapped_bench.append(str(future_mid.id))
    moved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": swapped_starters,
            "benchAthleteIds": swapped_bench,
        },
    )
    assert moved.status_code == 200
    assert moved.json()["tacticalMovesUsed"] == 1

    first_fixture.kickoff_at = datetime.now(UTC) + timedelta(days=2)
    first_fixture.status_short = "PST"
    db_session.commit()

    # EP-turni-automazione: il ricalcolo cutoff è ora azione da operatore.
    from auth.models.user import User
    from database.enums import PlatformRole

    operator = db_session.get(User, user_id)
    assert operator is not None
    operator.platform_role = PlatformRole.OPERATOR
    db_session.commit()

    recalc = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/ricalcola-cutoff",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recalc.status_code == 200

    context = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert context.status_code == 200
    body = context.json()
    roster_by_id = {row["athleteId"]: row for row in body["roster"]}
    assert roster_by_id[str(locked_gk.id)]["locked"] is True
    assert roster_by_id[str(locked_gk.id)]["lockLatched"] is True
    assert body["tacticalMovesUsed"] == 1
    assert body["tacticalMovesRemaining"] == 2

    moved_locked = list(swapped_starters)
    moved_locked[0] = str(grouped["P"][1].id)
    locked_bench = [item for item in swapped_bench if item != str(grouped["P"][1].id)]
    locked_bench.append(str(locked_gk.id))
    rejected = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": moved_locked,
            "benchAthleteIds": locked_bench,
        },
    )
    assert rejected.status_code == 400
    assert rejected.json()["code"] == "athlete_kickoff_locked"

    after = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert after.json()["tacticalMovesUsed"] == 1


def test_postponement_before_kickoff_keeps_player_editable(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "lineup.postpone.before@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Rinvio Prima")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=2_920_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)

    first_kickoff = datetime.now(UTC) + timedelta(hours=3)
    later_kickoff = datetime.now(UTC) + timedelta(hours=6)
    fantasy_round, clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=first_kickoff,
        extra_kickoff=later_kickoff,
        id_offset=2_930_000,
        competition_ids=competition_ids,
    )
    first_gk = grouped["P"][0]
    _set_athlete_club(db_session, first_gk, clubs[0])

    payload = _lineup_payload(athletes, "4-3-3")
    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert saved.status_code == 200

    fixtures = _round_fixtures(db_session, fantasy_round.id)
    first_fixture = next(item for item in fixtures if item.home_club_id == clubs[0].id)
    first_fixture.kickoff_at = datetime.now(UTC) + timedelta(hours=8)
    first_fixture.status_short = "PST"
    db_session.commit()

    context = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert context.status_code == 200
    roster_by_id = {row["athleteId"]: row for row in context.json()["roster"]}
    assert roster_by_id[str(first_gk.id)]["locked"] is False
    assert roster_by_id[str(first_gk.id)]["lockLatched"] is False

    moved = list(payload["starterAthleteIds"])
    moved[0] = str(grouped["P"][1].id)
    bench = [item for item in payload["benchAthleteIds"] if item != str(grouped["P"][1].id)]
    bench.append(str(first_gk.id))
    allowed = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={"module": "4-3-3", "starterAthleteIds": moved, "benchAthleteIds": bench},
    )
    assert allowed.status_code == 200
    assert allowed.json()["tacticalMovesUsed"] == 0


def test_concurrent_identical_lineup_saves_produce_single_revision(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """EP12-02: N richieste concorrenti che salvano la STESSA formazione per la
    stessa squadra/turno devono produrre un solo submission con revision=1 e un
    solo evento di audit, senza righe LineupPlayer duplicate. Il lock a riga su
    FantasyRound/FantasyTeam (``_load_round``/``_lock_team_for_membership``)
    serializza le richieste; la seconda in poi trova già salvata la stessa
    formazione (stessa signature) e ritorna senza incrementare la revision.
    """
    token, _ = _register_and_login(client, "lineup.conc@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Concorrenza Formazione")
    client.get(f"/leagues/{league_id}/rosa", headers={"Authorization": f"Bearer {token}"})
    grouped = _seed_roster_athletes(db_session, id_offset=2_950_000)
    athletes = _fill_validated_roster(db_session, league_id, grouped)
    cutoff = datetime.now(UTC) + timedelta(hours=4)
    fantasy_round, _clubs = _create_open_round(
        db_session,
        league_id,
        cutoff=cutoff,
        id_offset=2_960_000,
        competition_ids=competition_ids,
    )
    payload = _lineup_payload(athletes, "4-3-3")

    def _save(_index: int) -> int:
        response = client.put(
            f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(_save, range(6)))

    assert statuses.count(200) == 6

    team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).one()
    submissions = db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == fantasy_round.id,
            LineupSubmission.fantasy_team_id == team.id,
        )
    ).all()
    assert len(submissions) == 1
    submission = submissions[0]
    assert submission.revision == 1

    player_athlete_ids = db_session.scalars(
        select(LineupPlayer.athlete_id).where(LineupPlayer.submission_id == submission.id)
    ).all()
    assert len(player_athlete_ids) == len(set(player_athlete_ids)) == 35

    saved_count = db_session.scalar(
        select(func.count(LeagueAuditEvent.id)).where(
            LeagueAuditEvent.league_id == UUID(league_id),
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_SAVED,
        )
    )
    assert saved_count == 1
