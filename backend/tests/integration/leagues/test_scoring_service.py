"""Integration tests for H2H scoring, standings and homologation (EP07-05/06/07)."""

from __future__ import annotations

import json
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.exceptions import ValidationAuthError
from auth.models.user import User
from database.enums import (
    FantasyRoundHomologationStatus,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueAuditAction,
    LeagueCalendarStatus,
    LeagueMemberRole,
    LeagueState,
    LineupSlotKind,
    PlatformRole,
)
from database.session import create_session_factory
from fantasy_lineups.models import LineupPlayer, LineupSubmission
from fantasy_lineups.substitution_service import compute_round_effective_lineups
from fantasy_ratings.service import compute_fixture_ratings
from fantasy_teams.models import FantasyTeam
from fantasy_turns.homologation_service import apply_round_correction, homologate_round
from fantasy_turns.live_pipeline import process_live_fantasy_rounds
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.h2h_matchday_service import get_h2h_calendar
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import LeagueCalendar, LeagueCalendarSlot
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.models.league_standing import LeagueStanding
from leagues.scoring import fantasy_goals_for_points
from leagues.scoring_service import compute_round_results
from leagues.standings_service import compute_league_standings
from sports_data.catalog.sync import TeamsBatch, sync_catalog
from sports_data.fixtures.models import Fixture, PlayerMatchStat
from sports_data.fixtures.sync import FixtureDetailBatch, sync_fixtures
from sports_data.provider.envelope import parse_envelope
from sports_data.roster.models import Athlete

DATASET = Path(__file__).resolve().parents[2] / "fixtures" / "api_football"

# West Ham (home, club 48), modulo 4-5-1: stessa formazione di EP07-04
# (Fornals senza voto, sostituito da Benrahma).
WEST_HAM_STARTERS = [
    (253, "P"),
    (1231, "D"),
    (2726, "D"),
    (21694, "D"),
    (2284, "D"),
    (1243, "C"),
    (2938, "C"),
    (19428, "C"),
    (1646, "C"),
    (1697, "C"),  # Fornals, senza voto
    (18819, "A"),
]
WEST_HAM_BENCH = [(2869, "C"), (19361, "C"), (18817, "D")]

# Chelsea (away, club 49), modulo 3-4-3: undici titolari tutti con voto,
# nessuna sostituzione necessaria.
CHELSEA_STARTERS = [
    (18959, "P"),
    (21998, "D"),
    (259, "D"),
    (152953, "D"),
    (161907, "C"),
    (5996, "C"),
    (67972, "C"),
    (2933, "C"),
    (645, "A"),
    (138935, "A"),
    (283058, "A"),
]
CHELSEA_BENCH = [(63577, "C"), (116117, "C"), (136723, "A")]


@pytest.fixture()
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _load(rel: str) -> dict:
    return json.loads((DATASET / rel).read_text(encoding="utf-8"))


def _seed_catalog(session: Session) -> None:
    leagues = parse_envelope(_load("reference/leagues.json"), endpoint="/leagues", http_status=200)
    teams = parse_envelope(_load("reference/teams.json"), endpoint="/teams", http_status=200)
    sync_catalog(
        session,
        leagues_envelope=leagues,
        teams_batches=[TeamsBatch(envelope=teams, competition_provider_id=39, season_year=2026)],
    )


def _sync_match(session: Session) -> Fixture:
    fixtures_env = parse_envelope(
        _load("matches/39/1035055/fixtures.json"),
        endpoint="/fixtures",
        http_status=200,
    )
    details = [
        FixtureDetailBatch(
            fixture_provider_id=1035055,
            events_envelope=parse_envelope(
                _load("matches/39/1035055/fixtures_events.json"),
                endpoint="/fixtures/events",
                http_status=200,
            ),
            lineups_envelope=parse_envelope(
                _load("matches/39/1035055/fixtures_lineups.json"),
                endpoint="/fixtures/lineups",
                http_status=200,
            ),
            players_envelope=parse_envelope(
                _load("matches/39/1035055/fixtures_players.json"),
                endpoint="/fixtures/players",
                http_status=200,
            ),
        ),
    ]
    sync_fixtures(session, fixtures_envelopes=[fixtures_env], detail_batches=details)
    return session.execute(select(Fixture).where(Fixture.provider_id == 1035055)).scalar_one()


def _make_user(session: Session) -> User:
    now = datetime.now(UTC)
    user = User(
        email=f"coach-{uuid4()}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=now,
    )
    session.add(user)
    session.flush()
    return user


def _make_lineup(
    session: Session,
    *,
    league_id,
    round_id,
    team_id,
    user_id,
    module: str,
    starters: list[tuple[int, str]],
    bench: list[tuple[int, str]],
    athletes_by_provider_id: dict[int, Athlete],
) -> None:
    now = datetime.now(UTC)
    submission = LineupSubmission(
        league_id=league_id,
        round_id=round_id,
        fantasy_team_id=team_id,
        module=module,
        submitted_at=now,
        submitted_by_user_id=user_id,
    )
    session.add(submission)
    session.flush()
    for order, (provider_id, role) in enumerate(starters):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athletes_by_provider_id[provider_id].id,
                slot_kind=LineupSlotKind.STARTER,
                role=role,
                sort_order=order,
            )
        )
    for order, (provider_id, role) in enumerate(bench):
        session.add(
            LineupPlayer(
                submission_id=submission.id,
                athlete_id=athletes_by_provider_id[provider_id].id,
                slot_kind=LineupSlotKind.BENCH,
                role=role,
                sort_order=order,
            )
        )


def _build_two_team_round(session: Session, fixture: Fixture) -> tuple[FantasyRound, dict]:
    now = datetime.now(UTC)
    west_ham_user = _make_user(session)
    chelsea_user = _make_user(session)

    league = League(name="Lega Scontro Diretto", season_year=2026, state=LeagueState.ACTIVE)
    session.add(league)
    session.flush()
    session.add(LeagueRules(league_id=league.id))
    session.add(
        LeagueMembership(league_id=league.id, user_id=west_ham_user.id, role=LeagueMemberRole.OWNER)
    )
    session.add(
        LeagueMembership(league_id=league.id, user_id=chelsea_user.id, role=LeagueMemberRole.MEMBER)
    )
    session.flush()
    west_ham_membership = session.scalars(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == west_ham_user.id,
        )
    ).one()
    chelsea_membership = session.scalars(
        select(LeagueMembership).where(
            LeagueMembership.league_id == league.id,
            LeagueMembership.user_id == chelsea_user.id,
        )
    ).one()

    west_ham_team = FantasyTeam(
        league_id=league.id, membership_id=west_ham_membership.id, name="West Ham Fantasy"
    )
    chelsea_team = FantasyTeam(
        league_id=league.id, membership_id=chelsea_membership.id, name="Chelsea Fantasy"
    )
    session.add(west_ham_team)
    session.add(chelsea_team)
    session.flush()

    fantasy_round = FantasyRound(
        league_id=league.id,
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now,
        window_end_at=now + timedelta(days=3),
        status=FantasyTurnStatus.LOCKED,
        generated_at=now,
    )
    session.add(fantasy_round)
    session.flush()
    session.add(
        FantasyRoundFixture(round_id=fantasy_round.id, league_id=league.id, fixture_id=fixture.id)
    )

    calendar = LeagueCalendar(
        league_id=league.id,
        status=LeagueCalendarStatus.CONFIRMED,
        algorithm_version="test",
        participant_fingerprint="test",
        participant_count=4,
        round_count=1,
        matchup_count=1,
        bye_count=0,
        generated_at=now,
        confirmed_at=now,
    )
    session.add(calendar)
    session.flush()
    session.add(
        LeagueCalendarSlot(
            calendar_id=calendar.id,
            round_number=1,
            slot_index=0,
            is_bye=False,
            home_membership_id=west_ham_membership.id,
            away_membership_id=chelsea_membership.id,
        )
    )

    provider_ids = [
        pid for pid, _ in [*WEST_HAM_STARTERS, *WEST_HAM_BENCH, *CHELSEA_STARTERS, *CHELSEA_BENCH]
    ]
    athletes_by_provider_id = {
        row.provider_id: row
        for row in session.scalars(
            select(Athlete).where(Athlete.provider_id.in_(provider_ids))
        ).all()
    }

    _make_lineup(
        session,
        league_id=league.id,
        round_id=fantasy_round.id,
        team_id=west_ham_team.id,
        user_id=west_ham_user.id,
        module="4-5-1",
        starters=WEST_HAM_STARTERS,
        bench=WEST_HAM_BENCH,
        athletes_by_provider_id=athletes_by_provider_id,
    )
    _make_lineup(
        session,
        league_id=league.id,
        round_id=fantasy_round.id,
        team_id=chelsea_team.id,
        user_id=chelsea_user.id,
        module="3-4-3",
        starters=CHELSEA_STARTERS,
        bench=CHELSEA_BENCH,
        athletes_by_provider_id=athletes_by_provider_id,
    )
    session.commit()
    return fantasy_round, {"west_ham": west_ham_team, "chelsea": chelsea_team}


def test_compute_round_results_real_h2h(db_session: Session) -> None:
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()

    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    db_session.commit()

    result = compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()

    assert result.matchups == 1
    assert result.counters.created == 1
    assert result.counters.skipped == 0
    assert result.result_final is True  # fixture status_short == "FT"

    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == fantasy_round.league_id)
    ).one()
    slot = db_session.scalars(
        select(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
    ).one()

    assert slot.home_score is not None
    assert slot.away_score is not None
    assert slot.home_fantasy_goals == fantasy_goals_for_points(slot.home_score)
    assert slot.away_fantasy_goals == fantasy_goals_for_points(slot.away_score)
    assert slot.outcome in {"home", "away", "draw"}
    assert slot.result_final is True
    assert slot.result_computed_at is not None

    # Ricalcolo deterministico: nessun cambiamento.
    again = compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()
    assert again.counters.created == 0
    assert again.counters.updated == 0
    assert again.counters.unchanged == 1


def test_compute_round_results_skips_team_without_effective_lineup(db_session: Session) -> None:
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()

    fantasy_round, _teams = _build_two_team_round(db_session, fixture)
    # Nessun EffectiveLineup calcolato: la precondizione FR-SCO-03
    # ("sostituzioni calcolate") non è soddisfatta.
    result = compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()

    assert result.matchups == 1
    assert result.counters.skipped == 1
    assert result.counters.created == 0


def test_compute_round_results_updates_standings(db_session: Session) -> None:
    """EP07-05→EP07-06: il calcolo risultati aggiorna la classifica automaticamente."""
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()

    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    db_session.commit()
    compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()

    standings = {
        row.fantasy_team_id: row
        for row in db_session.scalars(
            select(LeagueStanding).where(LeagueStanding.league_id == fantasy_round.league_id)
        ).all()
    }
    assert len(standings) == 2
    assert standings[teams["west_ham"].id].played == 1
    assert standings[teams["chelsea"].id].played == 1


def test_compute_league_standings_after_round_results(db_session: Session) -> None:
    """EP07-06: la classifica riflette il risultato finale dello scontro diretto."""
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()

    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    db_session.commit()
    compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()

    result = compute_league_standings(db_session, league_id=fantasy_round.league_id)
    db_session.commit()

    assert result.teams == 2
    assert result.matches_considered == 1
    # Già popolata da compute_round_results; il secondo passaggio è idempotente.
    assert result.counters.created == 0
    assert result.counters.unchanged == 2

    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == fantasy_round.league_id)
    ).one()
    slot = db_session.scalars(
        select(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
    ).one()

    standings = {
        row.fantasy_team_id: row
        for row in db_session.scalars(
            select(LeagueStanding).where(LeagueStanding.league_id == fantasy_round.league_id)
        ).all()
    }
    west_ham_standing = standings[teams["west_ham"].id]
    chelsea_standing = standings[teams["chelsea"].id]

    assert west_ham_standing.played == 1
    assert chelsea_standing.played == 1
    assert west_ham_standing.fantasy_goals_for == slot.home_fantasy_goals
    assert west_ham_standing.fantasy_goals_against == slot.away_fantasy_goals
    assert chelsea_standing.fantasy_goals_for == slot.away_fantasy_goals
    assert chelsea_standing.fantasy_goals_against == slot.home_fantasy_goals
    # Le due posizioni sono 1 e 2 in ordine coerente con l'esito.
    assert {west_ham_standing.position, chelsea_standing.position} == {1, 2}
    if slot.outcome == "home":
        assert west_ham_standing.points == 3 and chelsea_standing.points == 0
        assert west_ham_standing.position == 1
    elif slot.outcome == "away":
        assert chelsea_standing.points == 3 and west_ham_standing.points == 0
        assert chelsea_standing.position == 1
    else:
        assert west_ham_standing.points == 1 and chelsea_standing.points == 1

    # Ricalcolo: nessun accumulo, i valori restano identici.
    again = compute_league_standings(db_session, league_id=fantasy_round.league_id)
    db_session.commit()
    assert again.counters.created == 0
    assert again.counters.updated == 0
    assert again.counters.unchanged == 2
    refreshed = db_session.scalars(
        select(LeagueStanding).where(
            LeagueStanding.league_id == fantasy_round.league_id,
            LeagueStanding.fantasy_team_id == teams["west_ham"].id,
        )
    ).one()
    assert refreshed.played == 1


def test_live_pipeline_keeps_provisional_then_finalizes_once(db_session: Session) -> None:
    """Provider -> voti -> sostituzioni -> H2H -> classifica -> omologazione.

    Durante il live i punteggi sono consultabili ma non valgono ancora in
    classifica. Solo lo snapshot terminale con statistiche giocatore rende il
    risultato definitivo; i poll successivi non riapplicano la giornata.
    """
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    fixture.status_short = "1H"
    db_session.commit()
    fantasy_round, teams = _build_two_team_round(db_session, fixture)

    live = process_live_fantasy_rounds(db_session)
    db_session.commit()

    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == fantasy_round.league_id)
    ).one()
    slot = db_session.scalars(
        select(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
    ).one()
    standings = {
        row.fantasy_team_id: row
        for row in db_session.scalars(
            select(LeagueStanding).where(LeagueStanding.league_id == fantasy_round.league_id)
        ).all()
    }

    assert live.rounds_processed >= 1
    assert live.rounds_finalized == 0
    assert slot.home_score is not None and slot.away_score is not None
    assert slot.result_final is False
    live_calendar = get_h2h_calendar(db_session, league_id=fantasy_round.league_id)
    assert live_calendar is not None
    assert live_calendar.live is True
    assert live_calendar.rounds[0].matchups[0].live is True
    assert standings[teams["west_ham"].id].played == 0
    assert standings[teams["chelsea"].id].played == 0
    assert (
        db_session.get(FantasyRound, fantasy_round.id).homologation_status
        == FantasyRoundHomologationStatus.PROVISIONAL
    )

    # Il provider può pubblicare FT prima che l'ultimo snapshot giocatori sia
    # completo. Con una sola squadra reale presente il risultato deve restare
    # provvisorio e la classifica non deve muoversi.
    db_session.execute(
        delete(PlayerMatchStat).where(
            PlayerMatchStat.fixture_id == fixture.id,
            PlayerMatchStat.club_id == fixture.away_club_id,
        )
    )
    fixture.status_short = "FT"
    db_session.commit()
    process_live_fantasy_rounds(db_session)
    db_session.commit()
    db_session.refresh(slot)
    assert slot.result_final is False
    assert (
        db_session.get(FantasyRound, fantasy_round.id).homologation_status
        == FantasyRoundHomologationStatus.PROVISIONAL
    )

    # Lo snapshot completo arriva al poll successivo: da qui la pipeline può
    # finalizzare in sicurezza.
    fixture = _sync_match(db_session)
    db_session.commit()
    final = process_live_fantasy_rounds(db_session)
    db_session.commit()
    db_session.refresh(slot)

    assert final.rounds_finalized >= 1
    assert slot.result_final is True
    final_calendar = get_h2h_calendar(db_session, league_id=fantasy_round.league_id)
    assert final_calendar is not None
    assert final_calendar.live is False
    assert final_calendar.rounds[0].matchups[0].live is False
    stored_round = db_session.get(FantasyRound, fantasy_round.id)
    assert stored_round.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED
    assert stored_round.homologated_by_user_id is None

    final_standings = {
        row.fantasy_team_id: row
        for row in db_session.scalars(
            select(LeagueStanding).where(LeagueStanding.league_id == fantasy_round.league_id)
        ).all()
    }
    assert final_standings[teams["west_ham"].id].played == 1
    assert final_standings[teams["chelsea"].id].played == 1
    before = {
        team_id: (row.played, row.points, row.fantasy_goals_for, row.fantasy_goals_against)
        for team_id, row in final_standings.items()
    }

    again = process_live_fantasy_rounds(db_session)
    db_session.commit()
    assert again.rounds_finalized == 0
    after = {
        row.fantasy_team_id: (
            row.played,
            row.points,
            row.fantasy_goals_for,
            row.fantasy_goals_against,
        )
        for row in db_session.scalars(
            select(LeagueStanding).where(LeagueStanding.league_id == fantasy_round.league_id)
        ).all()
    }
    assert after == before

    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == fantasy_round.league_id,
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROUND_HOMOLOGATED,
        )
    ).one()
    assert audit.actor_id is None
    assert audit.details["source"] == "automatic_live_pipeline"

    # La fixture del corpus viene riusata dai test successivi: riapri il turno
    # dopo aver verificato l'idempotenza, senza alterare le asserzioni sopra.
    operator = _make_user(db_session)
    automatically_closed_round_ids = list(
        db_session.scalars(
            select(FantasyRound.id).where(
                FantasyRound.homologation_status
                == FantasyRoundHomologationStatus.HOMOLOGATED
            )
        ).all()
    )
    for closed_round_id in automatically_closed_round_ids:
        apply_round_correction(
            db_session,
            round_id=closed_round_id,
            actor_id=operator.id,
            reason="Ripristino stato provvisorio per isolamento test",
        )
    db_session.commit()


def _full_pipeline(db_session: Session) -> tuple[Fixture, FantasyRound, dict]:
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()
    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    db_session.commit()
    compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()
    return fixture, fantasy_round, teams


def test_homologate_round_requires_finished_fixtures(db_session: Session) -> None:
    operator = _make_user(db_session)
    db_session.commit()
    _, fantasy_round, _teams = _full_pipeline(db_session)

    # Sposta artificialmente la fixture fuori dallo stato "terminato".
    fixture = db_session.scalars(select(Fixture).where(Fixture.provider_id == 1035055)).one()
    fixture.status_short = "1H"
    db_session.commit()

    with pytest.raises(ValidationAuthError) as excinfo:
        homologate_round(db_session, round_id=fantasy_round.id, actor_id=operator.id)
    assert excinfo.value.code == "round_not_final"


def test_homologate_round_opens_the_next_scheduled_round(db_session: Session) -> None:
    """EP-turni-automazione: il "verdetto" (omologazione) apre il turno
    successivo senza aspettare il giro del cron orario — sia che il turno
    successivo sia programmato con cutoff futuro (si apre), sia che non sia
    ancora pronto (nessun errore, resta come sta)."""
    operator = _make_user(db_session)
    db_session.commit()
    _, fantasy_round, _teams = _full_pipeline(db_session)

    future_window = datetime.now(UTC) + timedelta(days=7)
    next_round = FantasyRound(
        league_id=fantasy_round.league_id,
        number=fantasy_round.number + 1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=future_window,
        window_end_at=future_window + timedelta(days=3),
        cutoff_at=future_window,
        status=FantasyTurnStatus.SCHEDULED,
        generated_at=datetime.now(UTC),
    )
    db_session.add(next_round)
    db_session.commit()

    homologate_round(db_session, round_id=fantasy_round.id, actor_id=operator.id)
    db_session.commit()

    db_session.refresh(next_round)
    assert next_round.status == FantasyTurnStatus.OPEN
    assert next_round.opens_at is not None

    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == fantasy_round.league_id,
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_TURN_OPENED,
        )
    ).one()
    assert audit.details["roundId"] == str(next_round.id)
    assert audit.details["auto"] is True
    assert audit.details["trigger"] == "homologation"

    apply_round_correction(
        db_session,
        round_id=fantasy_round.id,
        actor_id=operator.id,
        reason="Ripristino stato provvisorio per isolamento test",
    )
    db_session.commit()


def test_homologate_round_does_not_open_a_round_whose_cutoff_already_passed(
    db_session: Session,
) -> None:
    """Stessa guardia di `_try_auto_open`: un turno successivo il cui cutoff
    è già scaduto (es. omologazione arrivata tardi) resta SCHEDULED — non lo
    si apre già chiuso, evita di far credere ai fantallenatori che possano
    ancora schierare."""
    operator = _make_user(db_session)
    db_session.commit()
    _, fantasy_round, _teams = _full_pipeline(db_session)

    past_window = datetime.now(UTC) - timedelta(days=1)
    next_round = FantasyRound(
        league_id=fantasy_round.league_id,
        number=fantasy_round.number + 1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=past_window,
        window_end_at=past_window + timedelta(days=3),
        cutoff_at=past_window,
        status=FantasyTurnStatus.SCHEDULED,
        generated_at=datetime.now(UTC),
    )
    db_session.add(next_round)
    db_session.commit()

    homologate_round(db_session, round_id=fantasy_round.id, actor_id=operator.id)
    db_session.commit()

    db_session.refresh(next_round)
    assert next_round.status == FantasyTurnStatus.SCHEDULED

    apply_round_correction(
        db_session,
        round_id=fantasy_round.id,
        actor_id=operator.id,
        reason="Ripristino stato provvisorio per isolamento test",
    )
    db_session.commit()


def test_homologate_round_locks_data_and_correction_reopens_it(db_session: Session) -> None:
    """EP07-07 / FR-OMO-01: un turno omologato non cambia più; solo una
    correzione motivata e auditata lo riapre per un nuovo ricalcolo."""
    operator = _make_user(db_session)
    db_session.commit()
    fixture, fantasy_round, teams = _full_pipeline(db_session)

    result = homologate_round(db_session, round_id=fantasy_round.id, actor_id=operator.id)
    db_session.commit()
    assert result.homologation_status == "homologated"
    assert result.formula_version is not None

    stored = db_session.get(FantasyRound, fantasy_round.id)
    assert stored.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED
    assert stored.homologated_at is not None
    assert stored.homologated_by_user_id == operator.id
    assert stored.homologation_formula_version == result.formula_version

    # Un ricalcolo ordinario è bloccato su ognuno dei tre livelli della pipeline.
    with pytest.raises(ValidationAuthError) as excinfo:
        compute_fixture_ratings(db_session, fixture_id=fixture.id)
    assert excinfo.value.code == "round_homologated"

    with pytest.raises(ValidationAuthError) as excinfo:
        compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    assert excinfo.value.code == "round_homologated"

    with pytest.raises(ValidationAuthError) as excinfo:
        compute_round_results(db_session, round_id=fantasy_round.id)
    assert excinfo.value.code == "round_homologated"

    # Omologare due volte è rifiutato in modo esplicito (non silenzioso).
    with pytest.raises(ValidationAuthError) as excinfo:
        homologate_round(db_session, round_id=fantasy_round.id, actor_id=operator.id)
    assert excinfo.value.code == "round_already_homologated"

    # La correzione richiede un motivo.
    with pytest.raises(ValidationAuthError) as excinfo:
        apply_round_correction(
            db_session, round_id=fantasy_round.id, actor_id=operator.id, reason="   "
        )
    assert excinfo.value.code == "correction_reason_required"

    correction = apply_round_correction(
        db_session,
        round_id=fantasy_round.id,
        actor_id=operator.id,
        reason="Rettifica statistiche ufficiali del provider",
    )
    db_session.commit()
    assert correction.homologation_status == "provisional"

    stored = db_session.get(FantasyRound, fantasy_round.id)
    assert stored.homologation_status == FantasyRoundHomologationStatus.PROVISIONAL
    assert stored.homologated_at is None
    assert stored.homologated_by_user_id is None

    # Dopo la correzione, il ricalcolo torna ammesso su tutta la pipeline.
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    compute_round_effective_lineups(db_session, round_id=fantasy_round.id)
    compute_round_results(db_session, round_id=fantasy_round.id)
    db_session.commit()

    again = homologate_round(db_session, round_id=fantasy_round.id, actor_id=operator.id)
    db_session.commit()
    assert again.homologation_status == "homologated"

    audit_actions = [
        row[0]
        for row in db_session.execute(
            select(LeagueAuditEvent.action).where(
                LeagueAuditEvent.league_id == fantasy_round.league_id
            )
        ).all()
    ]
    assert audit_actions.count(LeagueAuditAction.FANTASY_ROUND_HOMOLOGATED) == 2
    assert audit_actions.count(LeagueAuditAction.FANTASY_ROUND_CORRECTION_APPLIED) == 1

    # Riporta il turno a provvisorio: il modulo riusa lo stesso match reale
    # del corpus (fixture 39/1035055, upsert per provider_id) in piu' test,
    # e il guard blocca il ricalcolo su QUALSIASI turno legato a una fixture
    # omologata, quindi lasciarlo omologato bloccherebbe i test successivi.
    apply_round_correction(
        db_session,
        round_id=fantasy_round.id,
        actor_id=operator.id,
        reason="Ripristino stato provvisorio per isolamento test",
    )
    db_session.commit()


def test_homologate_round_concurrent_requests_only_one_succeeds(
    db_session: Session, db_url: str
) -> None:
    """Test di concorrenza (EP07-07): due thread con connessioni separate
    provano a omologare lo stesso turno nella stessa finestra. La UPDATE
    condizionale (``WHERE homologation_status = 'provisional'``) e' atomica
    a livello di riga in Postgres: il secondo thread resta bloccato sul lock
    del primo finche' non committa, poi trova 0 righe e fallisce in modo
    esplicito — nessuna doppia assegnazione, nessun audit duplicato.
    """
    operator = _make_user(db_session)
    db_session.commit()
    _fixture, fantasy_round, _teams = _full_pipeline(db_session)

    engine = create_engine_for_url(db_url)
    session_a = create_session_factory(engine)()
    session_b = create_session_factory(engine)()

    results: dict[str, tuple[str, str | None]] = {}
    a_updated = threading.Event()
    b_about_to_attempt = threading.Event()

    def run_a() -> None:
        try:
            outcome = homologate_round(session_a, round_id=fantasy_round.id, actor_id=operator.id)
            a_updated.set()
            # Da' tempo a session_b di raggiungere la UPDATE e bloccarsi sul
            # lock di riga prima che session_a rilasci il lock con il commit.
            b_about_to_attempt.wait(timeout=5)
            time.sleep(0.2)
            session_a.commit()
            results["a"] = ("ok", outcome.homologation_status)
        except Exception as exc:  # pragma: no cover - fallimento inatteso nel thread
            session_a.rollback()
            results["a"] = ("error", str(exc))

    def run_b() -> None:
        a_updated.wait(timeout=5)
        b_about_to_attempt.set()
        try:
            homologate_round(session_b, round_id=fantasy_round.id, actor_id=operator.id)
            session_b.commit()
            results["b"] = ("ok", None)
        except ValidationAuthError as exc:
            session_b.rollback()
            results["b"] = ("error", exc.code)

    thread_a = threading.Thread(target=run_a)
    thread_b = threading.Thread(target=run_b)
    thread_a.start()
    thread_b.start()
    thread_a.join(timeout=10)
    thread_b.join(timeout=10)
    session_a.close()
    session_b.close()
    engine.dispose()

    assert results.get("a") == ("ok", "homologated")
    assert results.get("b") == ("error", "round_already_homologated")

    audit_count = db_session.scalar(
        select(func.count())
        .select_from(LeagueAuditEvent)
        .where(
            LeagueAuditEvent.league_id == fantasy_round.league_id,
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROUND_HOMOLOGATED,
        )
    )
    assert audit_count == 1
