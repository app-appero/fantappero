"""Formazione dopo uno scambio che lascia un esubero di ruolo (QA 19/11, P1 e P2).

Uno scambio sbilanciato (2 per 1, o un D per un C) segna come esubero il calciatore
in più (``exceeds_role_quota``): resta in rosa ma non è schierabile. La squadra deve
però poter schierare la formazione con gli altri; solo una rosa con uno slot vuoto
resta bloccata, come dopo uno svincolo a lega avviata.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import (
    FantasyRole,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueMemberRole,
    LeagueState,
    RosterCompositionStatus,
)
from database.session import create_session_factory
from fantasy_teams.composition_service import sync_team_composition_status
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, CompetitionSeasonClub, SportSeason
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete

#: Preset standard della lega: 3 P, 11 D, 11 C, 10 A su 35.
ROLE_QUOTAS = ((FantasyRole.P, 3), (FantasyRole.D, 11), (FantasyRole.C, 11), (FantasyRole.A, 10))


def _register_and_login(client: TestClient, email: str) -> tuple[str, UUID]:
    client.post(
        "/auth/register",
        json={"email": email, "password": "Password123!", "displayName": email.split("@")[0]},
    )
    match = re.search(r"token=([A-Za-z0-9_-]+)", get_captured_emails()[-1].message.text_body)
    assert match
    client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": "Password123!"})
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


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_clubs_and_round(
    db_session: Session,
    league_id: str,
    competition_ids: list[str],
    *,
    id_offset: int,
) -> tuple[FantasyRound, list[Club]]:
    """Due club per ciascuno dei tre campionati della lega (così la rosa li rappresenta
    tutti, regola dei 3 campionati) e un turno aperto con una partita per campionato."""
    now = datetime.now(UTC)
    kickoff = now + timedelta(days=2)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=kickoff - timedelta(days=1),
        window_end_at=kickoff + timedelta(days=3),
        cutoff_at=kickoff,
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now,
    )
    db_session.add(fantasy_round)
    db_session.flush()

    clubs: list[Club] = []
    for comp_index, raw_competition_id in enumerate(competition_ids):
        competition_id = UUID(raw_competition_id)
        season = db_session.scalars(
            select(SportSeason).where(
                SportSeason.competition_id == competition_id, SportSeason.year == 2026
            )
        ).first()
        if season is None:
            season = SportSeason(competition_id=competition_id, year=2026, is_current=True)
            db_session.add(season)
            db_session.flush()
        home = Club(
            provider_id=id_offset + comp_index * 2, name=f"Club SC {id_offset}-{comp_index}H"
        )
        away = Club(
            provider_id=id_offset + comp_index * 2 + 1, name=f"Club SC {id_offset}-{comp_index}A"
        )
        db_session.add_all([home, away])
        db_session.flush()
        for club in (home, away):
            db_session.add(CompetitionSeasonClub(sport_season_id=season.id, club_id=club.id))
        fixture = Fixture(
            provider_id=id_offset + 50_000 + comp_index,
            sport_season_id=season.id,
            home_club_id=home.id,
            away_club_id=away.id,
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
        clubs.extend([home, away])
    db_session.commit()
    db_session.refresh(fantasy_round)
    return fantasy_round, clubs


def _fill_full_roster(
    db_session: Session,
    team_id: str,
    clubs: list[Club],
    *,
    provider_offset: int,
    label: str,
) -> dict[FantasyRole, list[UUID]]:
    """35 calciatori con ruoli esatti, distribuiti sui club dei tre campionati."""
    slots = db_session.scalars(
        select(FantasyRosterSlot)
        .where(FantasyRosterSlot.fantasy_team_id == UUID(team_id))
        .order_by(FantasyRosterSlot.slot_index.asc())
    ).all()
    by_role: dict[FantasyRole, list[UUID]] = {role: [] for role, _ in ROLE_QUOTAS}
    index = 0
    for role, count in ROLE_QUOTAS:
        for position in range(count):
            athlete = Athlete(
                provider_id=provider_offset + index,
                canonical_name=f"{label} {role.value}{position + 1}",
            )
            db_session.add(athlete)
            db_session.flush()
            db_session.add(
                RoleAssignment(
                    athlete_id=athlete.id,
                    season_year=2026,
                    role=role,
                    mapping_version="v1.0.0",
                    provider_position_raw=role.value,
                    club_id=clubs[index % len(clubs)].id,
                )
            )
            slots[index].athlete_id = athlete.id
            slots[index].purchase_credits = 1
            by_role[role].append(athlete.id)
            index += 1
    db_session.commit()
    return by_role


def _trade_league(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
    *,
    prefix: str,
    id_offset: int,
) -> dict:
    """Lega avviata con due squadre a rosa completa e convalidata e un turno aperto."""
    token_a, _ = _register_and_login(client, f"{prefix}.a@example.com")
    token_b, user_b = _register_and_login(client, f"{prefix}.b@example.com")
    created = client.post(
        "/leagues",
        headers=_headers(token_a),
        json={"name": f"Lega {prefix}", "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert created.status_code == 201
    league_id = created.json()["id"]
    db_session.add(
        LeagueMembership(league_id=UUID(league_id), user_id=user_b, role=LeagueMemberRole.MEMBER)
    )
    db_session.commit()

    team_a = client.get(f"/leagues/{league_id}/rosa", headers=_headers(token_a)).json()["id"]
    team_b = client.get(f"/leagues/{league_id}/rosa", headers=_headers(token_b)).json()["id"]

    fantasy_round, clubs = _seed_clubs_and_round(
        db_session, league_id, competition_ids, id_offset=id_offset
    )
    roles_a = _fill_full_roster(
        db_session, team_a, clubs, provider_offset=id_offset + 1_000, label="SqA"
    )
    roles_b = _fill_full_roster(
        db_session, team_b, clubs, provider_offset=id_offset + 2_000, label="SqB"
    )

    league = db_session.get(League, UUID(league_id))
    assert league is not None
    league.state = LeagueState.ACTIVE
    db_session.flush()
    # Convalida vera (quote esatte e 3 campionati), non uno stato forzato.
    for team_id in (team_a, team_b):
        team = db_session.get(FantasyTeam, UUID(team_id))
        assert team is not None
        report = sync_team_composition_status(db_session, team, league=league)
        assert report.status == RosterCompositionStatus.VALIDATED, report.issues
    db_session.commit()

    role_of = {
        athlete_id: role
        for roles in (roles_a, roles_b)
        for role, ids in roles.items()
        for athlete_id in ids
    }
    return {
        "league_id": league_id,
        "round_id": str(fantasy_round.id),
        "token_a": token_a,
        "token_b": token_b,
        "team_a": team_a,
        "team_b": team_b,
        "roles_a": roles_a,
        "roles_b": roles_b,
        "role_of": role_of,
    }


def _trade(
    client: TestClient,
    setup: dict,
    *,
    offered: list[UUID],
    requested: list[UUID],
) -> None:
    league_id = setup["league_id"]
    proposal = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte",
        headers=_headers(setup["token_a"]),
        json={
            "recipientTeamId": setup["team_b"],
            "offeredAthleteIds": [str(item) for item in offered],
            "requestedAthleteIds": [str(item) for item in requested],
            "offeredCredits": 0,
            "requestedCredits": 0,
            "expiresAt": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
        },
    )
    assert proposal.status_code == 201, proposal.json()
    accepted = client.post(
        f"/leagues/{league_id}/mercato/scambi/proposte/{proposal.json()['id']}/accetta",
        headers=_headers(setup["token_b"]),
    )
    assert accepted.status_code == 200, accepted.json()
    assert accepted.json()["status"] == "accepted"


def _occupied_slots(db_session: Session, team_id: str) -> list[FantasyRosterSlot]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(FantasyRosterSlot).where(
                FantasyRosterSlot.fantasy_team_id == UUID(team_id),
                FantasyRosterSlot.athlete_id.is_not(None),
            )
        ).all()
    )


def _lineup_payload(
    slots: list[FantasyRosterSlot], role_of: dict[UUID, FantasyRole], *, include: UUID | None = None
) -> dict:
    """4-3-3 con la panchina attiva in regola (1P-3D-3C-3A nei primi 10) e il resto in coda.

    I calciatori in esubero restano fuori; ``include`` ne forza uno tra i titolari.
    """
    by_role: dict[FantasyRole, list[str]] = {role: [] for role, _ in ROLE_QUOTAS}
    for slot in sorted(slots, key=lambda row: row.slot_index):
        if slot.exceeds_role_quota and slot.athlete_id != include:
            continue
        by_role[role_of[slot.athlete_id]].append(str(slot.athlete_id))
    if include is not None:
        role_list = by_role[role_of[include]]
        role_list.remove(str(include))
        role_list.insert(0, str(include))
    starters = [
        *by_role[FantasyRole.P][:1],
        *by_role[FantasyRole.D][:4],
        *by_role[FantasyRole.C][:3],
        *by_role[FantasyRole.A][:3],
    ]
    active_bench = [
        *by_role[FantasyRole.P][1:2],
        *by_role[FantasyRole.D][4:7],
        *by_role[FantasyRole.C][3:6],
        *by_role[FantasyRole.A][3:6],
    ]
    used = {*starters, *active_bench}
    rest = [item for ids in by_role.values() for item in ids if item not in used]
    return {
        "module": "4-3-3",
        "starterAthleteIds": starters,
        "benchAthleteIds": active_bench + rest,
    }


def _lineup_url(setup: dict) -> str:
    return f"/leagues/{setup['league_id']}/turni/{setup['round_id']}/formazione"


def _assert_team_can_field_without_excess(
    client: TestClient,
    db_session: Session,
    setup: dict,
    *,
    team_id: str,
    token: str,
) -> None:
    slots = _occupied_slots(db_session, team_id)
    flagged = [slot.athlete_id for slot in slots if slot.exceeds_role_quota]
    assert flagged, "lo scambio doveva lasciare un esubero segnato"

    best = client.post(f"{_lineup_url(setup)}/migliore", headers=_headers(token))
    assert best.status_code == 200, best.json()
    draft = best.json()["draft"]
    assert draft is not None
    assert not set(map(str, flagged)) & {
        *draft["starterAthleteIds"],
        *draft["benchAthleteIds"],
    }

    saved = client.put(
        _lineup_url(setup), headers=_headers(token), json=_lineup_payload(slots, setup["role_of"])
    )
    assert saved.status_code == 200, saved.json()
    lineup = saved.json()["lineup"]
    assert len(lineup["starters"]) == 11
    fielded = {item["athleteId"] for item in (*lineup["starters"], *lineup["bench"])}
    assert not set(map(str, flagged)) & fielded

    # Il calciatore in esubero, invece, non è schierabile.
    with_excess = client.put(
        _lineup_url(setup),
        headers=_headers(token),
        json=_lineup_payload(slots, setup["role_of"], include=flagged[0]),
    )
    assert with_excess.status_code == 400
    assert with_excess.json()["code"] == "athlete_not_in_roster"


def test_two_for_one_trade_receiving_team_can_field_without_the_excess(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="sc.duexuno", id_offset=9_960_000
    )
    # A cede due centrocampisti per uno: B sale a 36 con un C in esubero.
    _trade(
        client,
        setup,
        offered=setup["roles_a"][FantasyRole.C][:2],
        requested=setup["roles_b"][FantasyRole.C][:1],
    )
    slots_b = _occupied_slots(db_session, setup["team_b"])
    assert len(slots_b) == 36
    assert sum(1 for slot in slots_b if slot.exceeds_role_quota) == 1

    _assert_team_can_field_without_excess(
        client, db_session, setup, team_id=setup["team_b"], token=setup["token_b"]
    )


def test_defender_for_midfielder_trade_both_teams_can_field_without_the_excess(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(client, db_session, competition_ids, prefix="sc.dxc", id_offset=9_970_000)
    # A dà un D e riceve un C: A ha 12 C (uno in esubero), B 12 D (uno in esubero).
    _trade(
        client,
        setup,
        offered=setup["roles_a"][FantasyRole.D][:1],
        requested=setup["roles_b"][FantasyRole.C][:1],
    )
    for team_key, token_key in (("team_b", "token_b"), ("team_a", "token_a")):
        slots = _occupied_slots(db_session, setup[team_key])
        assert len(slots) == 35
        assert sum(1 for slot in slots if slot.exceeds_role_quota) == 1
        _assert_team_can_field_without_excess(
            client, db_session, setup, team_id=setup[team_key], token=setup[token_key]
        )


def test_excess_player_does_not_unblock_a_roster_with_an_empty_slot(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="sc.vuoto", id_offset=9_980_000
    )
    # A cede due D per un C: resta a 34/35 e il C ricevuto è in esubero (12 C su 11).
    _trade(
        client,
        setup,
        offered=setup["roles_a"][FantasyRole.D][:2],
        requested=setup["roles_b"][FantasyRole.C][:1],
    )
    slots_a = _occupied_slots(db_session, setup["team_a"])
    assert len(slots_a) == 34
    assert sum(1 for slot in slots_a if slot.exceeds_role_quota) == 1

    saved = client.put(
        _lineup_url(setup),
        headers=_headers(setup["token_a"]),
        json=_lineup_payload(slots_a, setup["role_of"]),
    )
    assert saved.status_code == 400
    assert saved.json()["code"] == "roster_not_validated"
    best = client.post(f"{_lineup_url(setup)}/migliore", headers=_headers(setup["token_a"]))
    assert best.status_code == 400
    assert best.json()["code"] == "roster_not_validated"

    # B invece è a 36 con due D in esubero e nessuno slot vuoto: può schierare.
    _assert_team_can_field_without_excess(
        client, db_session, setup, team_id=setup["team_b"], token=setup["token_b"]
    )


def test_roster_and_team_list_agree_on_composition_status_after_a_trade(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    setup = _trade_league(
        client, db_session, competition_ids, prefix="sc.stato", id_offset=9_990_000
    )
    # A cede due C per uno: A resta a 34/35 senza esuberi, B ha un C in esubero.
    _trade(
        client,
        setup,
        offered=setup["roles_a"][FantasyRole.C][:2],
        requested=setup["roles_b"][FantasyRole.C][:1],
    )
    league_id = setup["league_id"]
    listed = client.get(f"/leagues/{league_id}/squadre", headers=_headers(setup["token_a"]))
    assert listed.status_code == 200
    stored = {item["id"]: item["compositionStatus"] for item in listed.json()}

    for team_key, token_key in (("team_a", "token_a"), ("team_b", "token_b")):
        rosa = client.get(f"/leagues/{league_id}/rosa", headers=_headers(setup[token_key]))
        assert rosa.status_code == 200
        assert rosa.json()["compositionStatus"] == stored[setup[team_key]]
    assert stored[setup["team_a"]] == RosterCompositionStatus.INCOMPLETE.value
