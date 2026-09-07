"""Integration tests for the self-service "apply best lineup" endpoint (EP-self-service).

`POST /leagues/{id}/turni/{roundId}/formazione/migliore` reuses the same
`ai_lineup_v1` heuristic as the AI-only automation (ADR-0005), but on-demand
for a human's own team, gated by `roster:edit` (not `league:admin`/
`global:operate`). It only ever writes to the **draft**, never the confirmed
lineup — mirroring "Copia formazione precedente".
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
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore Rosa Incompleta")
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
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore Turno Skippato")
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
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore Deterministica")
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
    bench = [athlete for role in ("P", "D", "C", "A") for athlete in grouped[role] if athlete.id not in starter_ids]
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
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore Titolare Bloccato")
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
    role_by_id = {str(athlete.id): role for role, athletes in grouped.items() for athlete in athletes}
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
    league_id = _create_league(client, token, competition_ids, "Lega Applica Migliore Panchina Bloccata")
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

    # L'ordine relativo di chi era già in panchina e vi resta non cambia:
    # solo chi arriva nuovo in panchina (ex titolare retrocesso) si accoda.
    confirmed_bench_ids = [str(athlete.id) for athlete in bench]
    carried = [aid for aid in draft["benchAthleteIds"] if aid in set(confirmed_bench_ids)]
    expected_order = [aid for aid in confirmed_bench_ids if aid in set(draft["benchAthleteIds"])]
    assert carried == expected_order


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
