"""Integration tests for the self-service "apply best lineup" endpoint (EP-self-service).

`POST /leagues/{id}/turni/{roundId}/formazione/migliore` reuses the same
`ai_lineup_v1` heuristic as the AI-only automation (ADR-0005), but on-demand
for a human's own team, gated by `roster:edit` (not `league:admin`/
`global:operate`). It only ever writes to the **draft**, never the confirmed
lineup — mirroring "Copia formazione precedente".
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from database.enums import (
    FantasyModule,
    FantasyRole,
    FantasyTurnKind,
    FantasyTurnStatus,
    LineupSlotKind,
    RosterCompositionStatus,
)
from database.session import create_session_factory
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from mail.capture import get_captured_emails
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture
from sports_data.listone.models import RoleAssignment
from sports_data.predicted.models import PredictedLineupPlayer, PredictedLineupSnapshot
from sports_data.roster.models import Athlete


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


def _create_league(client: TestClient, token: str, competition_ids: list[str], name: str) -> str:
    response = client.post(
        "/leagues",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "seasonYear": 2026, "competitionIds": competition_ids},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_roster_athletes(
    db_session: Session,
    *,
    id_offset: int,
    club_id: UUID | None = None,
) -> dict[str, list[Athlete]]:
    """Rosa completa (3-11-11-10). `club_id`, se dato, lega ogni atleta a un
    club con fixture nel turno: senza fixture nota `has_fixture` resta falso
    e `is_eligible` esclude il candidato dall'euristica IA (ai_selection.py)."""
    grouped: dict[str, list[Athlete]] = {"P": [], "D": [], "C": [], "A": []}
    counts = {FantasyRole.P: 3, FantasyRole.D: 11, FantasyRole.C: 11, FantasyRole.A: 10}
    provider_id = id_offset
    for role, count in counts.items():
        for index in range(count):
            athlete = Athlete(provider_id=provider_id, canonical_name=f"{role.value} {index + 1}")
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
                    club_id=club_id,
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


def _create_round(
    db_session: Session,
    league_id: str,
    *,
    cutoff: datetime,
    status: FantasyTurnStatus = FantasyTurnStatus.OPEN,
    id_offset: int,
    competition_ids: list[str],
) -> tuple[FantasyRound, UUID]:
    now = datetime.now(UTC)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
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

    home = Club(provider_id=id_offset, name=f"Club ABL {id_offset}-home")
    away = Club(provider_id=id_offset + 1, name=f"Club ABL {id_offset}-away")
    db_session.add_all([home, away])
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

    fixture_id_offset = id_offset + 50_000
    fixture = Fixture(
        provider_id=fixture_id_offset,
        sport_season_id=season.id,
        home_club_id=home.id,
        away_club_id=away.id,
        kickoff_at=cutoff,
        status_short="NS",
    )
    db_session.add(fixture)
    db_session.flush()
    db_session.add(
        FantasyRoundFixture(
            round_id=fantasy_round.id,
            league_id=UUID(league_id),
            fixture_id=fixture.id,
            observed_kickoff_at=cutoff,
        )
    )
    db_session.commit()
    db_session.refresh(fantasy_round)
    return fantasy_round, home.id


def _create_round_with_two_fixtures(
    db_session: Session,
    league_id: str,
    *,
    id_offset: int,
    competition_ids: list[str],
) -> tuple[FantasyRound, UUID, UUID]:
    """Un turno con due partite: una già iniziata (`early_club`, locked) e una
    non ancora (`late_club`, libera) — per testare che il lock progressivo si
    applichi solo a chi è davvero già in campo."""
    now = datetime.now(UTC)
    cutoff = now + timedelta(hours=4)
    fantasy_round = FantasyRound(
        league_id=UUID(league_id),
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=cutoff - timedelta(days=2),
        window_end_at=cutoff + timedelta(days=1),
        cutoff_at=cutoff,
        status=FantasyTurnStatus.OPEN,
        generated_at=now,
        opens_at=now,
    )
    db_session.add(fantasy_round)
    db_session.flush()

    early_home = Club(provider_id=id_offset, name=f"Club ABL {id_offset}-early-home")
    early_away = Club(provider_id=id_offset + 1, name=f"Club ABL {id_offset}-early-away")
    late_home = Club(provider_id=id_offset + 2, name=f"Club ABL {id_offset}-late-home")
    late_away = Club(provider_id=id_offset + 3, name=f"Club ABL {id_offset}-late-away")
    db_session.add_all([early_home, early_away, late_home, late_away])
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

    early_fixture = Fixture(
        provider_id=id_offset + 50_000,
        sport_season_id=season.id,
        home_club_id=early_home.id,
        away_club_id=early_away.id,
        kickoff_at=now - timedelta(hours=2),
        status_short="1H",
    )
    late_fixture = Fixture(
        provider_id=id_offset + 50_001,
        sport_season_id=season.id,
        home_club_id=late_home.id,
        away_club_id=late_away.id,
        kickoff_at=cutoff,
        status_short="NS",
    )
    db_session.add_all([early_fixture, late_fixture])
    db_session.flush()
    db_session.add_all(
        [
            FantasyRoundFixture(
                round_id=fantasy_round.id,
                league_id=UUID(league_id),
                fixture_id=early_fixture.id,
                observed_kickoff_at=early_fixture.kickoff_at,
            ),
            FantasyRoundFixture(
                round_id=fantasy_round.id,
                league_id=UUID(league_id),
                fixture_id=late_fixture.id,
                observed_kickoff_at=late_fixture.kickoff_at,
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(fantasy_round)
    return fantasy_round, early_home.id, late_home.id


def _confirm_submission_directly(
    db_session: Session,
    *,
    league_id: str,
    round_id: UUID,
    team_id: UUID,
    user_id: UUID,
    module: FantasyModule,
    starters: list[Athlete],
    bench: list[Athlete],
) -> LineupSubmission:
    """Scrive una formazione già confermata direttamente in DB, come se fosse
    stata salvata prima che una qualunque partita iniziasse — bypassa
    l'endpoint HTTP apposta, perché `save_my_lineup` rifiuterebbe di creare
    ORA una formazione con un titolare già bloccato (`assert_progressive_lock`
    tratta l'assenza di una formazione precedente come "non ancora titolare")."""
    submission = LineupSubmission(
        league_id=UUID(league_id),
        round_id=round_id,
        fantasy_team_id=team_id,
        module=module,
        revision=1,
        submitted_at=datetime.now(UTC),
        submitted_by_user_id=user_id,
        system_generated_ai=False,
    )
    db_session.add(submission)
    db_session.flush()
    for order, athlete in enumerate(starters):
        db_session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athlete.id,
                slot_kind=LineupSlotKind.STARTER,
                role=FantasyRole(athlete.canonical_name[0]),
                sort_order=order,
            )
        )
    for order, athlete in enumerate(bench):
        db_session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athlete.id,
                slot_kind=LineupSlotKind.BENCH,
                role=FantasyRole(athlete.canonical_name[0]),
                sort_order=order,
            )
        )
    db_session.commit()
    db_session.refresh(submission)
    return submission


def test_apply_best_lineup_populates_draft_not_confirmed_lineup(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "apply.best.happy@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore")
    fantasy_round, home_club_id = _create_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        id_offset=2_505_000,
        competition_ids=competition_ids,
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_500_000, club_id=home_club_id)
    _fill_validated_roster(db_session, league_id, grouped)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["lineup"] is None
    assert body["draft"] is not None
    assert body["draft"]["module"] == "4-3-3"
    assert len(body["draft"]["starterAthleteIds"]) == 11
    assert len(body["draft"]["benchAthleteIds"]) == 24


def test_apply_best_lineup_does_not_require_platform_operator(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """`roster:edit` suffices — contrast with the admin bulk endpoint's `global:operate`."""
    token, _ = _register_and_login(client, "apply.best.no-operator@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore Non Admin")
    fantasy_round, home_club_id = _create_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        id_offset=2_515_000,
        competition_ids=competition_ids,
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_510_000, club_id=home_club_id)
    _fill_validated_roster(db_session, league_id, grouped)
    headers = {"Authorization": f"Bearer {token}"}

    bulk = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazioni-ia",
        headers=headers,
    )
    assert bulk.status_code == 403

    self_service = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    assert self_service.status_code == 200, self_service.json()


def test_apply_best_lineup_requires_validated_roster(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "apply.best.unvalidated@example.com")
    league_id = _create_league(
        client, token, competition_ids, "Lega Applica Migliore Rosa Incompleta"
    )
    fantasy_round, _home_club_id = _create_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        id_offset=2_520_000,
        competition_ids=competition_ids,
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "roster_not_validated"


def test_apply_best_lineup_rejects_a_skipped_turn(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "apply.best.skipped@example.com")
    league_id = _create_league(
        client, token, competition_ids, "Lega Applica Migliore Turno Skippato"
    )
    fantasy_round, home_club_id = _create_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) - timedelta(days=1),
        status=FantasyTurnStatus.SKIPPED,
        id_offset=2_535_000,
        competition_ids=competition_ids,
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_530_000, club_id=home_club_id)
    _fill_validated_roster(db_session, league_id, grouped)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "turn_skipped"


def test_apply_best_lineup_is_deterministic_across_calls(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    token, _ = _register_and_login(client, "apply.best.deterministic@example.com")
    league_id = _create_league(
        client, token, competition_ids, "Lega Applica Migliore Deterministica"
    )
    fantasy_round, home_club_id = _create_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        id_offset=2_545_000,
        competition_ids=competition_ids,
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_540_000, club_id=home_club_id)
    _fill_validated_roster(db_session, league_id, grouped)
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    second = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["draft"]["starterAthleteIds"] == second.json()["draft"]["starterAthleteIds"]
    assert first.json()["draft"]["benchAthleteIds"] == second.json()["draft"]["benchAthleteIds"]


def _module_433_split(grouped: dict[str, list[Athlete]]) -> tuple[list[Athlete], list[Athlete]]:
    starters = [*grouped["P"][:1], *grouped["D"][:4], *grouped["C"][:3], *grouped["A"][:3]]
    starter_ids = {athlete.id for athlete in starters}
    by_remaining_role = {
        role: [athlete for athlete in grouped[role] if athlete.id not in starter_ids]
        for role in ("P", "D", "C", "A")
    }
    # Panchina attiva valida (1P-3D-3C-3A nei primi 10, v. fantasy_lineups.rules):
    # senza interleave per ruolo, un ruolo per volta viola la regola.
    quota = {"P": 1, "D": 3, "C": 3, "A": 3}
    bench = [
        athlete
        for role in ("P", "D", "C", "A")
        for athlete in by_remaining_role[role][: quota[role]]
    ]
    bench += [
        athlete
        for role in ("P", "D", "C", "A")
        for athlete in by_remaining_role[role][quota[role] :]
    ]
    return starters, bench


def test_apply_best_lineup_keeps_a_locked_injured_starter_in_place(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Un titolare confermato la cui partita è già iniziata resta titolare
    anche se nel frattempo risulta infortunato — l'euristica libera lo
    escluderebbe sempre (`is_eligible`), il vincolo di lock lo impedisce."""
    token, user_id = _register_and_login(client, "apply.best.locked-starter@example.com")
    league_id = _create_league(
        client, token, competition_ids, "Lega Applica Migliore Titolare Bloccato"
    )
    fantasy_round, early_club_id, late_club_id = _create_round_with_two_fixtures(
        db_session, league_id, id_offset=2_550_000, competition_ids=competition_ids
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_550_100, club_id=late_club_id)
    locked_starter = grouped["D"][0]
    db_session.execute(
        select(RoleAssignment).where(RoleAssignment.athlete_id == locked_starter.id)
    ).scalar_one().club_id = early_club_id
    locked_starter.injured = True
    db_session.commit()

    _fill_validated_roster(db_session, league_id, grouped)
    starters, bench = _module_433_split(grouped)
    team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).one()
    _confirm_submission_directly(
        db_session,
        league_id=league_id,
        round_id=fantasy_round.id,
        team_id=team.id,
        user_id=user_id,
        module=FantasyModule.M433,
        starters=starters,
        bench=bench,
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    assert response.status_code == 200, response.json()
    draft = response.json()["draft"]
    assert str(locked_starter.id) in draft["starterAthleteIds"]
    assert len(draft["starterAthleteIds"]) == 11

    # Il titolare bloccato è un difensore: deve finire in mezzo al blocco
    # difensori del template posizionale (1P-4D-3C-3A), non scavalcare il
    # portiere in testa alla lista — altrimenti il client (che legge
    # `starterAthleteIds` per posizione, non per ruolo) lo scambia per un
    # portiere e duplica un altro titolare nello slot che gli spetterebbe.
    role_by_id = {
        str(athlete.id): role for role, athletes in grouped.items() for athlete in athletes
    }
    starter_roles = [role_by_id[athlete_id] for athlete_id in draft["starterAthleteIds"]]
    assert starter_roles == ["P"] + ["D"] * 4 + ["C"] * 3 + ["A"] * 3
    assert len(set(draft["starterAthleteIds"])) == 11


def test_apply_best_lineup_never_promotes_a_locked_bench_player(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Un panchinaro confermato la cui partita è già iniziata resta in
    panchina — non può essere promosso titolare dall'euristica. L'ordine di
    panchina già confermato, per chi resta in panchina, non viene toccato."""
    token, user_id = _register_and_login(client, "apply.best.locked-bench@example.com")
    league_id = _create_league(
        client, token, competition_ids, "Lega Applica Migliore Panchina Bloccata"
    )
    fantasy_round, early_club_id, late_club_id = _create_round_with_two_fixtures(
        db_session, league_id, id_offset=2_560_000, competition_ids=competition_ids
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_560_100, club_id=late_club_id)
    locked_bench = grouped["D"][4]
    db_session.execute(
        select(RoleAssignment).where(RoleAssignment.athlete_id == locked_bench.id)
    ).scalar_one().club_id = early_club_id
    db_session.commit()

    _fill_validated_roster(db_session, league_id, grouped)
    starters, bench = _module_433_split(grouped)
    assert locked_bench.id in {athlete.id for athlete in bench}
    team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).one()
    _confirm_submission_directly(
        db_session,
        league_id=league_id,
        round_id=fantasy_round.id,
        team_id=team.id,
        user_id=user_id,
        module=FantasyModule.M433,
        starters=starters,
        bench=bench,
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    assert response.status_code == 200, response.json()
    draft = response.json()["draft"]
    assert str(locked_bench.id) not in draft["starterAthleteIds"]
    assert str(locked_bench.id) in draft["benchAthleteIds"]

    # Il bloccato tiene il suo posto e chi lo precede non cambia (davanti a un bloccato non si
    # entra e non si esce); i primi 10 restano in quota 1P·3D·3C·3A. Prima un panchinaro dei
    # primi 10 promosso titolare faceva scalare la panchina e al 10° posto saliva il primo della
    # tribuna, qualunque ruolo avesse (qui 2P·4D·2C·2A): bozza non salvabile (e2e 20/11).
    confirmed_bench_ids = [str(athlete.id) for athlete in bench]
    locked_index = confirmed_bench_ids.index(str(locked_bench.id))
    assert draft["benchAthleteIds"][: locked_index + 1] == confirmed_bench_ids[: locked_index + 1]
    role_of = {str(athlete.id): role for role, athletes in grouped.items() for athlete in athletes}
    first_ten = Counter(role_of[athlete_id] for athlete_id in draft["benchAthleteIds"][:10])
    assert first_ten == Counter({"P": 1, "D": 3, "C": 3, "A": 3})
    saved = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers=headers,
        json={
            "module": draft["module"],
            "starterAthleteIds": draft["starterAthleteIds"],
            "benchAthleteIds": draft["benchAthleteIds"],
        },
    )
    assert saved.status_code == 200, saved.json()


def test_saving_is_not_blocked_by_a_role_reclassified_after_kickoff(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Un titolare bloccato riclassificato dal listone dopo lo schieramento non
    deve invalidare a posteriori la formazione: vale il ruolo con cui è sceso
    in campo (lo stesso che usa il motore di sostituzioni), altrimenti resta
    non salvabile per sempre — il calciatore è bloccato e non sostituibile."""
    token, user_id = _register_and_login(client, "reclassified.after.kickoff@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Riclassificazione")
    fantasy_round, early_club_id, late_club_id = _create_round_with_two_fixtures(
        db_session, league_id, id_offset=2_580_000, competition_ids=competition_ids
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_580_100, club_id=late_club_id)

    # Un attaccante titolare gioca nella partita già iniziata: è bloccato.
    locked_forward = grouped["A"][0]
    db_session.execute(
        select(RoleAssignment).where(RoleAssignment.athlete_id == locked_forward.id)
    ).scalar_one().club_id = early_club_id
    db_session.commit()

    _fill_validated_roster(db_session, league_id, grouped)
    starters, bench = _module_433_split(grouped)
    team = db_session.scalars(
        select(FantasyTeam).where(FantasyTeam.league_id == UUID(league_id))
    ).one()
    _confirm_submission_directly(
        db_session,
        league_id=league_id,
        round_id=fantasy_round.id,
        team_id=team.id,
        user_id=user_id,
        module=FantasyModule.M433,
        starters=starters,
        bench=bench,
    )

    # Dopo il calcio d'inizio il listone lo riclassifica centrocampista.
    db_session.execute(
        select(RoleAssignment).where(RoleAssignment.athlete_id == locked_forward.id)
    ).scalar_one().role = FantasyRole.C
    db_session.commit()

    # Ri-salvare la stessa identica formazione deve continuare a funzionare.
    response = client.put(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "4-3-3",
            "starterAthleteIds": [str(a.id) for a in starters],
            "benchAthleteIds": [str(a.id) for a in bench],
        },
    )
    assert response.status_code == 200, response.json()


def _seed_predicted_absences(
    db_session: Session,
    *,
    round_id: UUID,
    absences: list[tuple[Athlete, bool, str]],
) -> None:
    """Formazione probabile validata con gli assenti dati: (atleta, blocca la scelta, etichetta)."""
    fixture_id = db_session.scalars(
        select(FantasyRoundFixture.fixture_id).where(FantasyRoundFixture.round_id == round_id)
    ).one()
    snapshot = PredictedLineupSnapshot(
        fixture_id=fixture_id,
        fotmob_match_id=None,
        lineup_type="predicted",
        source="fotmob",
        reliability="validated",
        warning_codes=[],
        fetched_at=datetime.now(UTC) - timedelta(hours=1),
        home_formation="4-3-3",
        players=[
            PredictedLineupPlayer(
                athlete_id=athlete.id,
                side="home",
                display_name=athlete.canonical_name,
                is_starter=False,
                is_unavailable=True,
                unavailability_type="injury" if blocks else "doubtful",
                unavailability_label=label,
                blocks_selection=blocks,
                sort_order=index,
            )
            for index, (athlete, blocks, label) in enumerate(absences, start=1)
        ],
    )
    db_session.add(snapshot)
    db_session.commit()


def _first_by_id(athletes: list[Athlete]) -> Athlete:
    """Il preferito della formula a parità di segnali (ordine per id, `ai_selection._sort_key`)."""
    return min(athletes, key=lambda athlete: str(athlete.id))


def test_apply_best_lineup_never_fields_a_player_shown_unavailable(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Rosario, 27/11 (Lega Tester, turno europeo): dopo «Applica formazione migliore» in campo
    c'erano Muñoz e Schlotterbeck, grigi. La formula guardava solo `Athlete.injured` e la
    partita nel turno, non le assenze della formazione probabile che sito e app mostrano in
    grigio. Qui il difensore e il centrocampista che la formula sceglierebbe per primi sono
    assenti (uno certo, uno in dubbio): restano in panchina, al loro posto entrano i
    disponibili dello stesso ruolo."""
    token, _ = _register_and_login(client, "apply.best.unavailable@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore Grigi")
    fantasy_round, home_club_id = _create_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        id_offset=2_565_000,
        competition_ids=competition_ids,
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_560_000, club_id=home_club_id)
    _fill_validated_roster(db_session, league_id, grouped)
    defender = _first_by_id(grouped["D"])
    midfielder = _first_by_id(grouped["C"])
    headers = {"Authorization": f"Bearer {token}"}
    url = f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore"

    # Senza assenze la formula li sceglie: è proprio il caso segnalato.
    before = client.post(url, headers=headers)
    assert before.status_code == 200, before.json()
    assert str(defender.id) in before.json()["draft"]["starterAthleteIds"]
    assert str(midfielder.id) in before.json()["draft"]["starterAthleteIds"]

    _seed_predicted_absences(
        db_session,
        round_id=fantasy_round.id,
        absences=[(defender, True, "Infortunato"), (midfielder, False, "In dubbio")],
    )

    response = client.post(url, headers=headers)
    assert response.status_code == 200, response.json()
    body = response.json()
    starters = body["draft"]["starterAthleteIds"]
    assert len(starters) == 11
    assert str(defender.id) not in starters
    assert str(midfielder.id) not in starters
    # Restano in rosa: in panchina, non spariti.
    assert {str(defender.id), str(midfielder.id)} <= set(body["draft"]["benchAthleteIds"])
    role_by_id = {
        str(athlete.id): role for role, athletes in grouped.items() for athlete in athletes
    }
    assert [role_by_id[athlete_id] for athlete_id in starters] == (
        ["P"] + ["D"] * 4 + ["C"] * 3 + ["A"] * 3
    )
    # Stessa regola del grigio in campo: il contesto li manda come indisponibili.
    hints = {row["athleteId"]: row["probableHint"] for row in body["roster"]}
    assert hints[str(defender.id)] == "unavailable"
    assert hints[str(midfielder.id)] == "unavailable"
    assert all(hints[athlete_id] != "unavailable" for athlete_id in starters)
    # 1.5: il campo nuovo distingue il «in dubbio» (arancione) dall'assente certo (grigio).
    doubts = {row["athleteId"]: row.get("probableDoubt") for row in body["roster"]}
    assert doubts[str(midfielder.id)] is True
    assert doubts[str(defender.id)] is False
    assert all(doubts[athlete_id] is False for athlete_id in starters)


def test_apply_best_lineup_says_which_roles_lack_available_players(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Se senza gli indisponibili il modulo non si completa, la formula non riempie il buco
    con un grigio: rifiuta e dice quanti disponibili mancano per ruolo, senza toccare la bozza.

    Dalla 1.5 gli «in dubbio» possono coprire un buco (ultima risorsa): qui gli assenti sono
    tutti certi, quindi il messaggio resta quello di prima."""
    token, _ = _register_and_login(client, "apply.best.unavailable-short@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore Corta")
    fantasy_round, home_club_id = _create_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        id_offset=2_575_000,
        competition_ids=competition_ids,
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_570_000, club_id=home_club_id)
    _fill_validated_roster(db_session, league_id, grouped)
    # 11 difensori, 8 assenti certi: ne restano 3 per un 4-3-3.
    _seed_predicted_absences(
        db_session,
        round_id=fantasy_round.id,
        absences=[(athlete, True, "Infortunato") for athlete in grouped["D"][:8]],
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "ai_lineup_incomplete"
    assert "4-3-3" in body["message"]
    assert "1 difensore" in body["message"]
    assert "indisponibili" in body["message"].lower()

    context = client.get(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione",
        headers=headers,
    )
    assert context.status_code == 200
    assert context.json()["draft"] is None


def test_apply_best_lineup_uses_a_doubtful_player_only_as_last_resort(
    client: TestClient,
    db_session: Session,
    competition_ids: list[str],
) -> None:
    """Rosario, 28/11 (1.5): un «in dubbio» può giocare. La formula lo usa solo se nel suo
    ruolo non c'è più un disponibile e solo per completare il modulo; gli assenti certi
    restano fuori. Qui degli 11 difensori 6 sono assenti certi, 2 in dubbio e 3 disponibili: per il
    4-3-3 entrano i 3 disponibili e un solo «in dubbio», mai un assente certo."""
    token, _ = _register_and_login(client, "apply.best.doubtful@example.com")
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore Dubbi")
    fantasy_round, home_club_id = _create_round(
        db_session,
        league_id,
        cutoff=datetime.now(UTC) + timedelta(hours=4),
        id_offset=2_595_000,
        competition_ids=competition_ids,
    )
    grouped = _seed_roster_athletes(db_session, id_offset=2_590_000, club_id=home_club_id)
    _fill_validated_roster(db_session, league_id, grouped)
    defenders = sorted(grouped["D"], key=lambda athlete: str(athlete.id))
    # I primi per la formula (a parità di segnali vince l'id) sono gli «in dubbio» e i certi:
    # senza la regola nuova entrerebbero prima dei disponibili.
    doubtful = defenders[:2]
    certain = defenders[2:8]
    available = defenders[8:]
    _seed_predicted_absences(
        db_session,
        round_id=fantasy_round.id,
        absences=[
            *((athlete, False, "Doubtful") for athlete in doubtful),
            *((athlete, True, "Infortunato") for athlete in certain),
        ],
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/leagues/{league_id}/turni/{fantasy_round.id}/formazione/migliore",
        headers=headers,
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    starters = set(body["draft"]["starterAthleteIds"])
    assert len(starters) == 11
    fielded = starters & {str(athlete.id) for athlete in grouped["D"]}
    assert len(fielded) == 4
    assert {str(athlete.id) for athlete in available} <= fielded
    assert len(fielded & {str(athlete.id) for athlete in doubtful}) == 1
    assert not fielded & {str(athlete.id) for athlete in certain}
    # L'«in dubbio» rimasto fuori sta in panchina, davanti agli assenti certi dello stesso ruolo.
    bench = body["draft"]["benchAthleteIds"]
    left_out = next(str(a.id) for a in doubtful if str(a.id) not in starters)
    assert bench.index(left_out) < min(bench.index(str(athlete.id)) for athlete in certain)

    # Compatibilità: per l'app 1.4 l'«in dubbio» resta "unavailable" (grigio) e selezionabile.
    rows = {row["athleteId"]: row for row in body["roster"]}
    for athlete in doubtful:
        row = rows[str(athlete.id)]
        assert row["probableHint"] == "unavailable"
        assert row["probableAbsence"] == "other"
        assert row["selectionBlocked"] is False
        assert row["probableDoubt"] is True
    for athlete in certain:
        row = rows[str(athlete.id)]
        assert row["probableHint"] == "unavailable"
        assert row["probableAbsence"] == "injured"
        assert row["probableDoubt"] is False
