"""Formazione automatica IA sul database reale (EP13-P05 / ADR-0005)."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from auth.security import create_access_token
from database.enums import (
    FantasyRole,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueAuditAction,
    LeagueMemberRole,
    LeagueState,
    LineupSlotKind,
    PlatformRole,
    UserType,
)
from database.session import create_session_factory
from fantasy_lineups.ai_service import generate_ai_lineup
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.competition import Competition
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from sports_data.catalog.models import Club, SportSeason
from sports_data.fixtures.models import Fixture, OfficialLineup, OfficialLineupEntry
from sports_data.listone.models import RoleAssignment
from sports_data.roster.models import Athlete, SquadMembership

NOW = datetime(2026, 8, 22, 18, 0, tzinfo=UTC)

#: 4-3-3 → 1 portiere, 4 difensori, 3 centrocampisti, 3 attaccanti.
ROLE_PLAN = [
    (FantasyRole.P, 2),
    (FantasyRole.D, 6),
    (FantasyRole.C, 5),
    (FantasyRole.A, 5),
]


@pytest.fixture
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def scenario(db_session: Session) -> dict[str, object]:
    """Lega con una squadra IA, una umana, un turno e una partita."""
    seed = int(datetime.now(UTC).timestamp() * 1000) % 500_000

    ai_user = User(
        email=f"ai-{seed}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=NOW,
        user_type=UserType.AI,
    )
    human_user = User(
        email=f"human-{seed}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=NOW,
        user_type=UserType.HUMAN,
    )
    db_session.add_all([ai_user, human_user])
    db_session.flush()

    league = League(name=f"Lega IA {seed}", season_year=2026, state=LeagueState.ACTIVE)
    db_session.add(league)
    db_session.flush()
    db_session.add(LeagueRules(league_id=league.id))

    ai_m = LeagueMembership(league_id=league.id, user_id=ai_user.id, role=LeagueMemberRole.MEMBER)
    human_m = LeagueMembership(
        league_id=league.id, user_id=human_user.id, role=LeagueMemberRole.OWNER
    )
    db_session.add_all([ai_m, human_m])
    db_session.flush()

    ai_team = FantasyTeam(league_id=league.id, membership_id=ai_m.id, name="IA FC")
    human_team = FantasyTeam(league_id=league.id, membership_id=human_m.id, name="Umano FC")
    db_session.add_all([ai_team, human_team])
    db_session.flush()

    fantasy_round = FantasyRound(
        league_id=league.id,
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=NOW - timedelta(days=1),
        window_end_at=NOW + timedelta(days=2),
        cutoff_at=NOW + timedelta(hours=2),
        status=FantasyTurnStatus.OPEN,
        generated_at=NOW - timedelta(days=1),
    )
    db_session.add(fantasy_round)
    db_session.flush()

    competition = db_session.scalars(select(Competition)).first()
    assert competition is not None
    season = db_session.scalars(
        select(SportSeason).where(
            SportSeason.competition_id == competition.id, SportSeason.year == 2026
        )
    ).first()
    if season is None:
        season = SportSeason(competition_id=competition.id, year=2026, is_current=True)
        db_session.add(season)
        db_session.flush()

    home = Club(provider_id=seed + 1, name="Club IA A")
    away = Club(provider_id=seed + 2, name="Club IA B")
    db_session.add_all([home, away])
    db_session.flush()

    fixture = Fixture(
        provider_id=seed + 10,
        sport_season_id=season.id,
        home_club_id=home.id,
        away_club_id=away.id,
        kickoff_at=NOW + timedelta(hours=3),
        status_short="NS",
    )
    db_session.add(fixture)
    db_session.flush()
    db_session.add(
        FantasyRoundFixture(
            round_id=fantasy_round.id,
            league_id=league.id,
            fixture_id=fixture.id,
            observed_kickoff_at=fixture.kickoff_at,
        )
    )

    # Rosa IA: abbastanza giocatori per un 4-3-3 completo.
    athletes: list[Athlete] = []
    slot_index = 0
    for role, count in ROLE_PLAN:
        for i in range(count):
            athlete = Athlete(
                provider_id=seed * 10 + slot_index,
                canonical_name=f"{role.value}{i} Test",
                injured=False,
            )
            db_session.add(athlete)
            db_session.flush()
            membership_row = SquadMembership(
                athlete_id=athlete.id,
                club_id=home.id,
                sport_season_id=season.id,
                is_active=True,
            )
            db_session.add(membership_row)
            db_session.flush()
            # Il ruolo effettivo si risolve dal listone, non dalla rosa.
            db_session.add(
                RoleAssignment(
                    athlete_id=athlete.id,
                    season_year=2026,
                    role=role,
                    mapping_version="test",
                    squad_membership_id=membership_row.id,
                    club_id=home.id,
                )
            )
            db_session.add(
                FantasyRosterSlot(
                    fantasy_team_id=ai_team.id,
                    league_id=league.id,
                    slot_index=slot_index,
                    athlete_id=athlete.id,
                )
            )
            athletes.append(athlete)
            slot_index += 1

    db_session.commit()
    return {
        "league": league,
        "round": fantasy_round,
        "ai_team": ai_team,
        "human_team": human_team,
        "athletes": athletes,
        "fixture": fixture,
        "home_club": home,
    }


def test_ai_lineup_is_generated_and_marked_as_automatic(
    db_session: Session, scenario: dict[str, object]
) -> None:
    league = scenario["league"]
    fantasy_round = scenario["round"]
    ai_team = scenario["ai_team"]

    result = generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW,
    )
    db_session.commit()

    assert result.outcome == "created"
    # Il nome squadra viaggia con l'esito: l'admin che rigenera più squadre
    # IA da un turno deve poter distinguere quale riga è quale.
    assert result.fantasy_team_name == "IA FC"
    submission = db_session.execute(
        select(LineupSubmission).where(LineupSubmission.fantasy_team_id == ai_team.id)
    ).scalar_one()

    assert submission.system_generated_ai is True
    assert submission.ai_algorithm_version == "ai_lineup_v1"
    assert submission.ai_decided_at is not None
    assert submission.ai_decision_log is not None

    starters = db_session.scalars(
        select(LineupPlayer).where(
            LineupPlayer.submission_id == submission.id,
            LineupPlayer.slot_kind == LineupSlotKind.STARTER,
        )
    ).all()
    assert len(starters) == 11


def test_ai_lineup_never_touches_a_human_team(
    db_session: Session, scenario: dict[str, object]
) -> None:
    """Il guard centrale di ADR-0005 §7."""
    league = scenario["league"]
    fantasy_round = scenario["round"]
    human_team = scenario["human_team"]

    result = generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=human_team.id,
        now=NOW,
    )
    assert result.outcome == "skipped_not_ai"
    assert (
        db_session.execute(
            select(LineupSubmission).where(LineupSubmission.fantasy_team_id == human_team.id)
        ).scalar_one_or_none()
        is None
    )


def test_admin_endpoint_is_authorized_audited_and_human_safe(
    client: TestClient,
    db_session: Session,
    scenario: dict[str, object],
) -> None:
    league = scenario["league"]
    fantasy_round = scenario["round"]
    fixture = scenario["fixture"]
    ai_team = scenario["ai_team"]
    human_team = scenario["human_team"]

    # L'endpoint usa l'orologio reale: porta il turno seedato nella sua
    # finestra attiva, mantenendo lo stesso scenario deterministico di rosa.
    now = datetime.now(UTC)
    fantasy_round.window_start_at = now - timedelta(hours=1)
    fantasy_round.window_end_at = now + timedelta(days=1)
    fantasy_round.cutoff_at = now + timedelta(hours=2)
    fixture.kickoff_at = now + timedelta(hours=3)
    db_session.commit()

    ai_member = ai_team.membership.user
    owner = human_team.membership.user
    jwt_secret = os.environ.get("JWT_SECRET_KEY", "test_jwt_secret_for_pytest_only")
    member_token, _ = create_access_token(
        user_id=ai_member.id,
        secret=jwt_secret,
        expire_minutes=15,
    )
    owner_token, _ = create_access_token(
        user_id=owner.id,
        secret=jwt_secret,
        expire_minutes=15,
    )
    endpoint = f"/leagues/{league.id}/turni/{fantasy_round.id}/formazioni-ia"

    forbidden = client.post(
        endpoint,
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert forbidden.status_code == 403

    response = client.post(
        endpoint,
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["roundId"] == str(fantasy_round.id)
    assert payload["teams"][0]["fantasyTeamId"] == str(ai_team.id)
    assert payload["teams"][0]["outcome"] == "created"
    assert "1/1" in payload["summary"]

    assert db_session.scalars(
        select(LineupSubmission).where(LineupSubmission.fantasy_team_id == ai_team.id)
    ).one()
    assert (
        db_session.scalars(
            select(LineupSubmission).where(LineupSubmission.fantasy_team_id == human_team.id)
        ).one_or_none()
        is None
    )

    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == league.id,
            LeagueAuditEvent.actor_id == owner.id,
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_LINEUP_SAVED,
        )
    ).one()
    assert audit.details["source"] == "admin_ai_lineup_command"
    assert audit.details["roundId"] == str(fantasy_round.id)
    assert audit.details["teamsHandled"] == 1

def test_decision_log_records_scores_and_exclusions(
    db_session: Session, scenario: dict[str, object]
) -> None:
    """Senza log ispezionabile la scelta non sarebbe contestabile."""
    league = scenario["league"]
    fantasy_round = scenario["round"]
    ai_team = scenario["ai_team"]
    athletes = scenario["athletes"]

    # Un infortunato: deve comparire escluso, non schierato.
    injured = athletes[0]
    injured.injured = True
    db_session.commit()

    generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW,
    )
    db_session.commit()

    submission = db_session.execute(
        select(LineupSubmission).where(LineupSubmission.fantasy_team_id == ai_team.id)
    ).scalar_one()
    log = submission.ai_decision_log
    assert log["algorithmVersion"] == "ai_lineup_v1"

    by_id = {item["athleteId"]: item for item in log["candidates"]}
    assert by_id[str(injured.id)]["excludedReason"] == "injured"
    assert by_id[str(injured.id)]["excludedLabel"] == "Infortunato"

    starters = {
        str(p.athlete_id)
        for p in submission.players
        if p.slot_kind == LineupSlotKind.STARTER
    }
    assert str(injured.id) not in starters
    # Come nel percorso umano, tutta la rosa rimane registrata: l'infortunato
    # è in fondo alla panchina ma non può entrare negli undici iniziali.
    assert str(injured.id) in {str(p.athlete_id) for p in submission.players}


def test_official_lineup_without_provenance_is_ignored(
    db_session: Session, scenario: dict[str, object]
) -> None:
    """Distinta senza `fetched_at`: nessun segnale di titolarità (ADR-0005 §4)."""
    league = scenario["league"]
    fantasy_round = scenario["round"]
    ai_team = scenario["ai_team"]
    athletes = scenario["athletes"]
    fixture = scenario["fixture"]
    home_club = scenario["home_club"]

    lineup = OfficialLineup(
        fixture_id=fixture.id,
        club_id=home_club.id,
        formation="4-3-3",
        fetched_at=None,
    )
    db_session.add(lineup)
    db_session.flush()
    db_session.add(
        OfficialLineupEntry(
            lineup_id=lineup.id,
            athlete_id=athletes[0].id,
            athlete_provider_id=athletes[0].provider_id,
            is_starter=True,
            sort_order=0,
        )
    )
    db_session.commit()

    generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW,
    )
    db_session.commit()

    submission = db_session.execute(
        select(LineupSubmission).where(LineupSubmission.fantasy_team_id == ai_team.id)
    ).scalar_one()
    by_id = {item["athleteId"]: item for item in submission.ai_decision_log["candidates"]}
    # Il segnale non è stato usato: nessuna fonte `official_lineup`.
    assert "official_lineup" not in by_id[str(athletes[0].id)]["sources"]


def test_official_lineup_fetched_before_decision_is_used(
    db_session: Session, scenario: dict[str, object]
) -> None:
    league = scenario["league"]
    fantasy_round = scenario["round"]
    ai_team = scenario["ai_team"]
    athletes = scenario["athletes"]
    fixture = scenario["fixture"]
    home_club = scenario["home_club"]

    lineup = OfficialLineup(
        fixture_id=fixture.id,
        club_id=home_club.id,
        formation="4-3-3",
        fetched_at=NOW - timedelta(hours=1),
    )
    db_session.add(lineup)
    db_session.flush()
    db_session.add(
        OfficialLineupEntry(
            lineup_id=lineup.id,
            athlete_id=athletes[0].id,
            athlete_provider_id=athletes[0].provider_id,
            is_starter=True,
            sort_order=0,
        )
    )
    db_session.commit()

    generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW,
    )
    db_session.commit()

    submission = db_session.execute(
        select(LineupSubmission).where(LineupSubmission.fantasy_team_id == ai_team.id)
    ).scalar_one()
    by_id = {item["athleteId"]: item for item in submission.ai_decision_log["candidates"]}
    assert "official_lineup" in by_id[str(athletes[0].id)]["sources"]


def test_generation_is_deterministic_across_runs(
    db_session: Session, scenario: dict[str, object]
) -> None:
    league = scenario["league"]
    fantasy_round = scenario["round"]
    ai_team = scenario["ai_team"]

    first = generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW,
        dry_run=True,
    )
    second = generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW,
        dry_run=True,
    )
    assert first.plan is not None and second.plan is not None
    assert first.plan.starters == second.plan.starters
    assert first.plan.bench == second.plan.bench


def test_identical_persisted_generation_is_a_true_noop(
    db_session: Session, scenario: dict[str, object]
) -> None:
    league = scenario["league"]
    fantasy_round = scenario["round"]
    ai_team = scenario["ai_team"]

    first = generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW,
    )
    db_session.commit()
    assert first.outcome == "created"

    submission = db_session.scalars(
        select(LineupSubmission).where(LineupSubmission.fantasy_team_id == ai_team.id)
    ).one()
    original_revision = submission.revision
    original_submitted_at = submission.submitted_at

    second = generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW + timedelta(minutes=5),
    )
    db_session.commit()

    assert second.outcome == "unchanged"
    db_session.refresh(submission)
    assert submission.revision == original_revision
    assert submission.submitted_at == original_submitted_at


def test_dry_run_does_not_persist_anything(
    db_session: Session, scenario: dict[str, object]
) -> None:
    league = scenario["league"]
    fantasy_round = scenario["round"]
    ai_team = scenario["ai_team"]

    result = generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW,
        dry_run=True,
    )
    assert result.outcome == "preview"
    assert (
        db_session.execute(
            select(LineupSubmission).where(LineupSubmission.fantasy_team_id == ai_team.id)
        ).scalar_one_or_none()
        is None
    )


def test_unknown_round_is_rejected(db_session: Session, scenario: dict[str, object]) -> None:
    from auth.exceptions import ValidationAuthError

    league = scenario["league"]
    ai_team = scenario["ai_team"]
    with pytest.raises(ValidationAuthError) as excinfo:
        generate_ai_lineup(
            db_session,
            league_id=league.id,
            round_id=uuid4(),
            fantasy_team_id=ai_team.id,
            now=NOW,
        )
    assert excinfo.value.code == "turn_not_found"


def test_locked_players_are_not_dropped_on_a_second_run(
    db_session: Session, scenario: dict[str, object]
) -> None:
    """Regressione: riscrivere dopo il lock cancellerebbe i bloccati.

    Il piano esclude per costruzione chi ha la partita già iniziata; senza il
    guard, il secondo giro li rimuoverebbe dalla formazione invece di
    lasciarli intatti (ADR-0005 §6).
    """
    league = scenario["league"]
    fantasy_round = scenario["round"]
    ai_team = scenario["ai_team"]
    fixture = scenario["fixture"]

    first = generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW,
    )
    db_session.commit()
    assert first.outcome == "created"

    submission = db_session.execute(
        select(LineupSubmission).where(LineupSubmission.fantasy_team_id == ai_team.id)
    ).scalar_one()
    fielded_before = {p.athlete_id for p in submission.players}
    assert len(fielded_before) > 0

    # La partita inizia: tutti i calciatori di quel club si bloccano.
    fixture.status_short = "1H"
    db_session.commit()

    second = generate_ai_lineup(
        db_session,
        league_id=league.id,
        round_id=fantasy_round.id,
        fantasy_team_id=ai_team.id,
        now=NOW + timedelta(hours=4),
    )
    db_session.commit()

    assert second.outcome == "skipped_locked"
    db_session.expire_all()
    submission = db_session.execute(
        select(LineupSubmission).where(LineupSubmission.fantasy_team_id == ai_team.id)
    ).scalar_one()
    assert {p.athlete_id for p in submission.players} == fielded_before
