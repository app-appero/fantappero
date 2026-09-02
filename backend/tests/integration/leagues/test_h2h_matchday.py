"""Integration coverage for H2H matchday read endpoints (calendario/h2h + scontro)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from auth.models.user import User
from database.enums import (
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueCalendarStatus,
    LeagueMemberRole,
    LeagueState,
    PlatformRole,
)
from database.session import create_session_factory
from fantasy_teams.models import FantasyTeam
from fantasy_turns.models import FantasyRound
from leagues.h2h_matchday_service import get_h2h_calendar, get_h2h_matchup_detail
from leagues.models.league import League
from leagues.models.league_calendar import (
    LeagueCalendar,
    LeagueCalendarRoundWindow,
    LeagueCalendarSlot,
)
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules


@pytest.fixture()
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_user(session: Session, label: str) -> User:
    user = User(
        email=f"{label}-{uuid4()}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    session.flush()
    return user


def test_h2h_calendar_and_matchup_detail_mapping(db_session: Session) -> None:
    now = datetime.now(UTC)
    home_user = _make_user(db_session, "home")
    away_user = _make_user(db_session, "away")
    bye_user = _make_user(db_session, "bye")

    league = League(name="Lega H2H Read", season_year=2026, state=LeagueState.ACTIVE)
    db_session.add(league)
    db_session.flush()
    db_session.add(LeagueRules(league_id=league.id))

    home_m = LeagueMembership(
        league_id=league.id, user_id=home_user.id, role=LeagueMemberRole.OWNER
    )
    away_m = LeagueMembership(
        league_id=league.id, user_id=away_user.id, role=LeagueMemberRole.MEMBER
    )
    bye_m = LeagueMembership(
        league_id=league.id, user_id=bye_user.id, role=LeagueMemberRole.MEMBER
    )
    db_session.add_all([home_m, away_m, bye_m])
    db_session.flush()

    home_team = FantasyTeam(league_id=league.id, membership_id=home_m.id, name="Casa FC")
    away_team = FantasyTeam(league_id=league.id, membership_id=away_m.id, name="Trasferta FC")
    bye_team = FantasyTeam(league_id=league.id, membership_id=bye_m.id, name="Riposo FC")
    db_session.add_all([home_team, away_team, bye_team])
    db_session.flush()

    fantasy_round = FantasyRound(
        league_id=league.id,
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now,
        window_end_at=now + timedelta(days=3),
        status=FantasyTurnStatus.OPEN,
        cutoff_at=now + timedelta(hours=2),
        generated_at=now,
    )
    db_session.add(fantasy_round)
    db_session.flush()

    calendar = LeagueCalendar(
        league_id=league.id,
        status=LeagueCalendarStatus.CONFIRMED,
        algorithm_version="circle_rr_v1",
        participant_fingerprint="test",
        participant_count=4,
        round_count=1,
        matchup_count=1,
        bye_count=1,
        generated_at=now,
        confirmed_at=now,
    )
    db_session.add(calendar)
    db_session.flush()

    match_slot = LeagueCalendarSlot(
        calendar_id=calendar.id,
        round_number=1,
        slot_index=0,
        is_bye=False,
        home_membership_id=home_m.id,
        away_membership_id=away_m.id,
        home_score=72.5,
        away_score=66.0,
        home_fantasy_goals=2,
        away_fantasy_goals=1,
        outcome="home",
        result_final=False,
        result_computed_at=now,
    )
    bye_slot = LeagueCalendarSlot(
        calendar_id=calendar.id,
        round_number=1,
        slot_index=1,
        is_bye=True,
        home_membership_id=bye_m.id,
        away_membership_id=None,
    )
    db_session.add_all([match_slot, bye_slot])
    db_session.commit()

    payload = get_h2h_calendar(db_session, league_id=league.id)
    assert payload is not None
    assert payload.live is True
    assert payload.round_count == 1
    assert len(payload.rounds) == 1
    round_row = payload.rounds[0]
    assert round_row.round_number == 1
    assert round_row.fantasy_round_id == str(fantasy_round.id)
    assert round_row.european_turn_status == "open"
    assert round_row.homologation_status == "provisional"
    assert len(round_row.matchups) == 2

    scored = next(item for item in round_row.matchups if not item.is_bye)
    assert scored.home_team_name == "Casa FC"
    assert scored.away_team_name == "Trasferta FC"
    assert scored.result is not None
    assert scored.result.home_fantasy_goals == 2
    assert scored.result.result_final is False

    bye = next(item for item in round_row.matchups if item.is_bye)
    assert bye.home_team_name == "Riposo FC"
    assert bye.result is None

    detail = get_h2h_matchup_detail(
        db_session,
        league_id=league.id,
        slot_id=match_slot.id,
    )
    assert detail.slot_id == str(match_slot.id)
    assert detail.fantasy_round_id == str(fantasy_round.id)
    assert detail.live is True
    assert detail.home.team_name == "Casa FC"
    assert detail.away is not None
    assert detail.away.team_name == "Trasferta FC"
    assert detail.result is not None
    assert detail.result.outcome == "home"

    assert get_h2h_calendar(db_session, league_id=uuid4()) is None


def test_skipped_european_window_does_not_consume_an_h2h_matchday(
    db_session: Session,
) -> None:
    """EP13-P03: la mappatura esplicita salta le finestre sotto soglia.

    Con l'abbinamento storico per numero progressivo, la giornata H2H 1
    finiva sul turno europeo 1 anche quando quello era ``skipped``, cioè su
    una giornata non giocabile. Con la mappatura per finestra la giornata 1
    prende il primo turno realmente disputabile.
    """
    now = datetime.now(UTC)
    home_user = _make_user(db_session, "map-home")
    away_user = _make_user(db_session, "map-away")

    league = League(name="Lega Mappatura", season_year=2026, state=LeagueState.ACTIVE)
    db_session.add(league)
    db_session.flush()
    db_session.add(LeagueRules(league_id=league.id))

    home_m = LeagueMembership(
        league_id=league.id, user_id=home_user.id, role=LeagueMemberRole.OWNER
    )
    away_m = LeagueMembership(
        league_id=league.id, user_id=away_user.id, role=LeagueMemberRole.MEMBER
    )
    db_session.add_all([home_m, away_m])
    db_session.flush()

    db_session.add_all(
        [
            FantasyTeam(league_id=league.id, membership_id=home_m.id, name="Casa FC"),
            FantasyTeam(league_id=league.id, membership_id=away_m.id, name="Trasferta FC"),
        ]
    )
    db_session.flush()

    # Turno 1 sotto soglia, turno 2 realmente giocabile.
    skipped_start = now
    playable_start = now + timedelta(days=7)
    skipped_round = FantasyRound(
        league_id=league.id,
        number=1,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=skipped_start,
        window_end_at=skipped_start + timedelta(days=3),
        status=FantasyTurnStatus.SKIPPED,
        skip_reason="Soglia non raggiunta: 3 partite eleggibili su 25 richieste.",
        generated_at=now,
    )
    playable_round = FantasyRound(
        league_id=league.id,
        number=2,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=playable_start,
        window_end_at=playable_start + timedelta(days=3),
        status=FantasyTurnStatus.OPEN,
        cutoff_at=playable_start + timedelta(hours=2),
        generated_at=now,
    )
    db_session.add_all([skipped_round, playable_round])
    db_session.flush()

    calendar = LeagueCalendar(
        league_id=league.id,
        status=LeagueCalendarStatus.CONFIRMED,
        algorithm_version="adaptive_windows_v2",
        participant_fingerprint="test-mapping",
        participant_count=4,
        round_count=1,
        matchup_count=1,
        bye_count=0,
        cycle_length=1,
        cycle_count=1,
        windows_fingerprint="fingerprint-test",
        generated_at=now,
        confirmed_at=now,
    )
    db_session.add(calendar)
    db_session.flush()

    db_session.add(
        LeagueCalendarSlot(
            calendar_id=calendar.id,
            round_number=1,
            slot_index=0,
            is_bye=False,
            home_membership_id=home_m.id,
            away_membership_id=away_m.id,
        )
    )
    db_session.add(
        LeagueCalendarRoundWindow(
            calendar_id=calendar.id,
            round_number=1,
            cycle_number=1,
            cycle_round_number=1,
            window_start_at=playable_round.window_start_at,
            window_end_at=playable_round.window_end_at,
            window_kind=FantasyTurnKind.WEEKEND.value,
        )
    )
    db_session.commit()

    payload = get_h2h_calendar(db_session, league_id=league.id)
    assert payload is not None
    round_row = payload.rounds[0]
    assert round_row.round_number == 1
    # Punto della card: NON il turno saltato.
    assert round_row.fantasy_round_id == str(playable_round.id)
    assert round_row.fantasy_round_id != str(skipped_round.id)
    assert round_row.european_turn_status == "open"

    slot_id = db_session.query(LeagueCalendarSlot).filter_by(calendar_id=calendar.id).one().id
    detail = get_h2h_matchup_detail(db_session, league_id=league.id, slot_id=slot_id)
    assert detail.fantasy_round_id == str(playable_round.id)
