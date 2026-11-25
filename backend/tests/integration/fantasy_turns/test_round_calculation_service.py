"""Integration tests for the unified round-calculation engine (EP-turni-calcolo)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url
from tests.integration.fantasy_turns.test_fantasy_turns import (
    _promote_to_operator,
    _register_and_login,
)
from tests.integration.leagues.test_scoring_service import (
    _build_two_team_round,
    _seed_catalog,
    _sync_match,
)

from auth.exceptions import ValidationAuthError
from database.enums import (
    FantasyRoundHomologationStatus,
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueAuditAction,
    LeagueState,
    LineupAutoResolutionSource,
)
from database.session import create_session_factory
from fantasy_lineups.models import LineupSubmission
from fantasy_ratings.service import compute_fixture_ratings
from fantasy_turns.live_pipeline import (
    LIVE_PIPELINE_HORIZON,
    process_live_fantasy_rounds,
    select_live_rounds,
)
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from fantasy_turns.round_calculation_service import calculate_league_round
from leagues.models.league import League
from leagues.models.league_audit_event import LeagueAuditEvent
from leagues.models.league_calendar import (
    LeagueCalendar,
    LeagueCalendarRoundWindow,
    LeagueCalendarSlot,
)
from leagues.models.league_membership import LeagueMembership
from market.round_freeze import league_round_in_progress
from notifications.models import Notification
from sports_data.fixtures.models import Fixture, PlayerMatchStat


@pytest.fixture()
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _prepare_scenario(db_session: Session) -> tuple[FantasyRound, dict, Fixture]:
    """Sincronizza la fixture reale e valuta i rating: da chiamare **una sola
    volta per modulo** (i test condividono lo stesso DB senza rollback tra
    l'uno e l'altro, e omologare un turno blocca per sempre il ricalcolo dei
    rating di quella fixture, in qualunque lega — `assert_fixture_not_homologated`).
    I test successivi devono riusare `_existing_fixture` invece di richiamare
    questa funzione."""
    _seed_catalog(db_session)
    db_session.commit()
    fixture = _sync_match(db_session)
    db_session.commit()
    compute_fixture_ratings(db_session, fixture_id=fixture.id)
    db_session.commit()
    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    return fantasy_round, teams, fixture


def _existing_fixture(db_session: Session) -> Fixture:
    return db_session.execute(select(Fixture).where(Fixture.provider_id == 1035055)).scalar_one()


def _drop_submission(db_session: Session, round_id, team_id) -> None:
    submission = db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == round_id,
            LineupSubmission.fantasy_team_id == team_id,
        )
    ).one()
    db_session.delete(submission)
    db_session.commit()


def _slot(db_session: Session, league_id) -> LeagueCalendarSlot:
    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == league_id)
    ).one()
    return db_session.scalars(
        select(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
    ).one()


def test_calculates_and_homologates_a_round_with_a_missing_lineup(db_session: Session) -> None:
    """Riproduce esattamente il bug reale osservato su 'Test lega': turno con
    partite concluse ma un fantallenatore senza formazione -> prima di questa
    feature restava bloccato per sempre; ora si risolve a 0 punti e omologa."""
    fantasy_round, teams, _fixture = _prepare_scenario(db_session)
    _drop_submission(db_session, fantasy_round.id, teams["chelsea"].id)

    result = calculate_league_round(
        db_session,
        round_id=fantasy_round.id,
        league_id=fantasy_round.league_id,
        actor_id=None,
        automatic=False,
    )
    db_session.commit()

    assert result.fallback is not None
    assert result.fallback.resolved_as_zero == 1
    assert result.result_final is True
    assert result.homologated is True

    refreshed = db_session.get(FantasyRound, fantasy_round.id)
    assert refreshed is not None
    assert refreshed.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED

    slot = _slot(db_session, fantasy_round.league_id)
    assert slot.result_final is True
    assert slot.away_score == 0.0  # Chelsea: nessuna formazione -> 0 punti
    assert slot.outcome in {"home", "draw"}  # mai "away": West Ham ha voti reali > 0

    chelsea_submission = db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == fantasy_round.id,
            LineupSubmission.fantasy_team_id == teams["chelsea"].id,
        )
    ).one()
    assert chelsea_submission.auto_resolution_source == LineupAutoResolutionSource.ZERO_FALLBACK
    assert chelsea_submission.players == []
    # Idempotenza del fallback in sé (senza toccare l'omologazione, che una
    # volta scattata blocca ogni ricalcolo dei rating della fixture) è già
    # coperta da test_fallback_service.py — chiamare due volte qui
    # richiederebbe una correzione (apply_round_correction), fuori scope.


def test_the_automatic_job_calls_the_same_engine_as_the_manual_command(
    db_session: Session,
) -> None:
    """EP-turni-calcolo requisito 9: nessuna logica divergente tra job e comando manuale.

    Riusa la fixture reale già sincronizzata e valutata dal test precedente
    (stesso modulo, stesso DB) su una NUOVA lega — evita di richiamare di
    nuovo `compute_fixture_ratings`, bloccato una volta che una qualsiasi
    lega ha già omologato un turno su questa fixture.
    """
    fixture = _existing_fixture(db_session)
    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    _drop_submission(db_session, fantasy_round.id, teams["chelsea"].id)

    pipeline_result = process_live_fantasy_rounds(db_session)
    db_session.commit()

    assert pipeline_result.rounds_processed == 1
    assert pipeline_result.rounds_finalized == 1

    refreshed = db_session.get(FantasyRound, fantasy_round.id)
    assert refreshed is not None
    assert refreshed.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED

    chelsea_submission = db_session.scalars(
        select(LineupSubmission).where(
            LineupSubmission.round_id == fantasy_round.id,
            LineupSubmission.fantasy_team_id == teams["chelsea"].id,
        )
    ).one()
    assert chelsea_submission.auto_resolution_source == LineupAutoResolutionSource.ZERO_FALLBACK


def test_calculate_round_endpoint_rejects_non_operator(
    client: TestClient,
    db_session: Session,
) -> None:
    token, _user_id = _register_and_login(client, "calcola-giornata.member@example.com")
    fixture = _existing_fixture(db_session)
    fantasy_round, _teams = _build_two_team_round(db_session, fixture)

    response = client.post(
        f"/leagues/{fantasy_round.league_id}/turni/{fantasy_round.id}/calcola-giornata",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_calculate_round_endpoint_matches_the_service_result_for_an_operator(
    client: TestClient,
    db_session: Session,
) -> None:
    token, user_id = _register_and_login(client, "calcola-giornata.operator@example.com")
    _promote_to_operator(db_session, user_id)
    fixture = _existing_fixture(db_session)
    fantasy_round, teams = _build_two_team_round(db_session, fixture)
    _drop_submission(db_session, fantasy_round.id, teams["chelsea"].id)

    response = client.post(
        f"/leagues/{fantasy_round.league_id}/turni/{fantasy_round.id}/calcola-giornata",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["roundId"] == str(fantasy_round.id)
    assert body["resultFinal"] is True
    assert body["homologated"] is True
    assert body["fallbackResolvedAsZero"] == 1

    # La chiamata HTTP ha omologato tramite una sessione DB separata da
    # db_session: bisogna scartare la identity map locale prima di rileggere.
    db_session.expire_all()
    refreshed = db_session.get(FantasyRound, fantasy_round.id)
    assert refreshed is not None
    assert refreshed.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED


def test_the_automatic_job_skips_rounds_whose_matches_are_too_old_to_change(
    db_session: Session,
) -> None:
    """QA notte 18-19/11: il job ricalcolava ogni 5 minuti tutti i turni mai omologati,
    anche vecchi di settimane, e teneva occupato il worker. Con l'orizzonte del job
    automatico il turno vecchio resta fuori; i comandi manuali (senza orizzonte) no."""
    fixture = _existing_fixture(db_session)
    fantasy_round, _teams = _build_two_team_round(db_session, fixture)
    pair = (fantasy_round.id, fantasy_round.league_id)
    kickoff = fixture.kickoff_at

    assert pair in select_live_rounds(
        db_session, horizon=LIVE_PIPELINE_HORIZON, now=kickoff + timedelta(hours=3)
    )
    assert pair not in select_live_rounds(
        db_session,
        horizon=LIVE_PIPELINE_HORIZON,
        now=kickoff + LIVE_PIPELINE_HORIZON + timedelta(minutes=1),
    )
    assert pair in select_live_rounds(db_session)


# -- Turni iniziati prima della creazione della lega (pilota, turno 11 del 20/11) --------------


@dataclass
class _PlaceholderLeague:
    league_id: UUID
    placeholder: FantasyRound  # turno 1: iniziato prima della creazione, nessuno scontro
    later: FantasyRound  # turno 2: dopo la creazione
    pending: Fixture  # partita del turno 1 ancora in corso
    user_ids: list[UUID]


def _new_fixture(
    db_session: Session, base: Fixture, *, provider_id: int, status: str, kickoff: datetime
) -> Fixture:
    fixture = Fixture(
        provider_id=provider_id,
        sport_season_id=base.sport_season_id,
        home_club_id=base.home_club_id,
        away_club_id=base.away_club_id,
        kickoff_at=kickoff,
        status_short=status,
    )
    db_session.add(fixture)
    db_session.flush()
    return fixture


def _finish_with_stats(db_session: Session, fixture: Fixture, source: Fixture) -> None:
    """La partita finisce e arrivano le statistiche giocatore (copiate da una partita vera)."""
    fixture.status_short = "FT"
    for stat in db_session.scalars(
        select(PlayerMatchStat).where(PlayerMatchStat.fixture_id == source.id)
    ).all():
        db_session.add(
            PlayerMatchStat(
                fixture_id=fixture.id,
                athlete_id=stat.athlete_id,
                athlete_provider_id=stat.athlete_provider_id,
                club_id=stat.club_id,
                minutes=stat.minutes,
                position_raw=stat.position_raw,
                is_substitute=stat.is_substitute,
                provider_rating=stat.provider_rating,
                stats_json=stat.stats_json,
                stats_hash=stat.stats_hash,
            )
        )
    db_session.commit()


def _placeholder_league(
    db_session: Session, *, with_calendar: bool, provider_offset: int, later_started: bool
) -> _PlaceholderLeague:
    """Lega creata 3 ore fa, a turno 1 già iniziato (finestra da ieri): il turno 1 è il
    segnaposto «Lega creata dopo questo turno»; il turno 2 inizia dopo la creazione.

    Con ``with_calendar`` il calendario è ancorato alle finestre come quelli veri: la giornata
    H2H 1 si gioca nel turno 2 e il turno 1 non ospita scontri. Senza, la lega non ha calendario
    (generazione rifiutata, come la lega delle 16:23 sul pilota).
    """
    base = _existing_fixture(db_session)
    fantasy_round, teams = _build_two_team_round(db_session, base)
    league = db_session.get(League, fantasy_round.league_id)
    assert league is not None
    now = datetime.now(UTC)
    league.created_at = now - timedelta(hours=3)
    fantasy_round.window_start_at = now - timedelta(days=1)
    fantasy_round.window_end_at = now - timedelta(hours=2)
    pending = _new_fixture(
        db_session,
        base,
        provider_id=provider_offset + 1,
        status="2H",
        kickoff=now - timedelta(days=1) + timedelta(hours=2),
    )
    db_session.add(
        FantasyRoundFixture(round_id=fantasy_round.id, league_id=league.id, fixture_id=pending.id)
    )
    later = FantasyRound(
        league_id=league.id,
        number=2,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=now - timedelta(minutes=90),
        window_end_at=now + timedelta(days=2),
        status=FantasyTurnStatus.SCHEDULED,
        generated_at=now,
    )
    db_session.add(later)
    db_session.flush()
    later_fixture = _new_fixture(
        db_session,
        base,
        provider_id=provider_offset + 2,
        status="2H" if later_started else "NS",
        kickoff=now - timedelta(hours=1) if later_started else now + timedelta(days=1),
    )
    db_session.add(
        FantasyRoundFixture(round_id=later.id, league_id=league.id, fixture_id=later_fixture.id)
    )
    calendar = db_session.scalars(
        select(LeagueCalendar).where(LeagueCalendar.league_id == league.id)
    ).one()
    if with_calendar:
        db_session.add(
            LeagueCalendarRoundWindow(
                calendar_id=calendar.id,
                round_number=1,
                cycle_number=1,
                cycle_round_number=1,
                window_start_at=later.window_start_at,
                window_end_at=later.window_end_at,
                window_kind="weekend",
            )
        )
    else:
        db_session.execute(
            delete(LeagueCalendarSlot).where(LeagueCalendarSlot.calendar_id == calendar.id)
        )
        db_session.delete(calendar)
    db_session.commit()
    user_ids = [
        user_id
        for (user_id,) in db_session.execute(
            select(LeagueMembership.user_id).where(LeagueMembership.league_id == league.id)
        ).all()
    ]
    return _PlaceholderLeague(
        league_id=league.id,
        placeholder=fantasy_round,
        later=later,
        pending=pending,
        user_ids=user_ids,
    )


def _calculate(db_session: Session, fantasy_round: FantasyRound):
    result = calculate_league_round(
        db_session,
        round_id=fantasy_round.id,
        league_id=fantasy_round.league_id,
        actor_id=None,
        automatic=True,
    )
    db_session.commit()
    return result


def test_round_started_before_the_league_is_homologated_without_h2h_once_data_are_final(
    db_session: Session,
) -> None:
    scenario = _placeholder_league(
        db_session, with_calendar=True, provider_offset=9_710_000, later_started=False
    )
    assert league_round_in_progress(db_session, scenario.league_id).id == scenario.placeholder.id

    # Una partita del turno è ancora in corso: niente omologazione.
    early = _calculate(db_session, scenario.placeholder)
    assert early.before_league_creation is True
    assert early.result_final is False
    assert early.homologated is False
    db_session.refresh(scenario.placeholder)
    assert scenario.placeholder.homologation_status == FantasyRoundHomologationStatus.PROVISIONAL

    # Partite finite e statistiche arrivate: omologato senza aspettare scontri che non ci sono.
    _finish_with_stats(db_session, scenario.pending, _existing_fixture(db_session))
    final = _calculate(db_session, scenario.placeholder)
    assert final.before_league_creation is True
    assert final.result_final is True
    assert final.homologated is True
    db_session.expire_all()
    placeholder = db_session.get(FantasyRound, scenario.placeholder.id)
    assert placeholder.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED

    # La giornata H2H 1 (ospitata dal turno 2) non è stata toccata.
    slot = _slot(db_session, scenario.league_id)
    assert slot.outcome is None
    assert slot.result_final is False

    # Effetti dell'omologazione come per un turno normale (audit, turno dopo, mercato di
    # nuovo aperto), ma nessuna notifica: quel turno la lega non l'ha giocato (QA 24-25/11).
    audit = db_session.scalars(
        select(LeagueAuditEvent).where(
            LeagueAuditEvent.league_id == scenario.league_id,
            LeagueAuditEvent.action == LeagueAuditAction.FANTASY_ROUND_HOMOLOGATED,
        )
    ).one()
    assert audit.details["roundId"] == str(scenario.placeholder.id)
    assert audit.details["source"] == "automatic_live_pipeline"
    assert audit.details["beforeLeagueCreation"] is True
    assert len(scenario.user_ids) == 2
    notifications = db_session.scalars(
        select(Notification).where(
            Notification.user_id.in_(scenario.user_ids),
            Notification.template_key == "risultati.omologazione",
        )
    ).all()
    assert notifications == []
    later = db_session.get(FantasyRound, scenario.later.id)
    assert later.status == FantasyTurnStatus.OPEN
    assert league_round_in_progress(db_session, scenario.league_id) is None


def test_rounds_after_the_league_creation_still_wait_for_their_h2h_results(
    db_session: Session,
) -> None:
    """Il turno 2 (dopo la creazione) ospita la giornata H2H 1: calcolo normale, nessuna
    scorciatoia. Senza formazioni per il turno lo scontro resta da risolvere."""
    scenario = _placeholder_league(
        db_session, with_calendar=True, provider_offset=9_720_000, later_started=False
    )
    result = _calculate(db_session, scenario.later)
    assert result.before_league_creation is False
    assert result.result_final is False
    assert result.homologated is False


def test_league_without_calendar_closes_only_the_round_before_its_creation(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """Pilota: la lega delle 16:23 del 20/11 non ha il calendario. Il suo turno 11 (iniziato
    prima della creazione) si omologa; i turni dopo la creazione continuano a segnalare
    ``calendar_not_found``, ora con turno, lega e codice nel testo del log. Senza calendario
    la lega non è partita: l'omologazione non apre il turno dopo («Schiera la formazione»)."""
    scenario = _placeholder_league(
        db_session, with_calendar=False, provider_offset=9_730_000, later_started=True
    )
    league = str(scenario.league_id)
    db_session.get(League, scenario.league_id).state = LeagueState.CONFIGURING
    db_session.commit()

    with caplog.at_level("WARNING", logger="fantasy_turns.live_pipeline"):
        first = process_live_fantasy_rounds(db_session)
    mine = [error for error in first.errors if error.get("leagueId") == league]
    assert mine == [
        {"roundId": str(scenario.later.id), "leagueId": league, "code": "calendar_not_found"}
    ]
    expected_line = f"round_id={scenario.later.id} league_id={league} code=calendar_not_found"
    assert f"fantasy_live_pipeline_round_skipped {expected_line}" in [
        record.getMessage() for record in caplog.records
    ]
    assert expected_line in first.error_lines()
    db_session.expire_all()
    placeholder = db_session.get(FantasyRound, scenario.placeholder.id)
    assert placeholder.homologation_status == FantasyRoundHomologationStatus.PROVISIONAL

    _finish_with_stats(
        db_session, db_session.get(Fixture, scenario.pending.id), _existing_fixture(db_session)
    )
    second = process_live_fantasy_rounds(db_session)
    db_session.expire_all()
    placeholder = db_session.get(FantasyRound, scenario.placeholder.id)
    assert placeholder.homologation_status == FantasyRoundHomologationStatus.HOMOLOGATED
    assert [error for error in second.errors if error.get("leagueId") == league] == mine
    assert db_session.get(FantasyRound, scenario.later.id).status == FantasyTurnStatus.SCHEDULED

    with pytest.raises(ValidationAuthError) as exc:
        _calculate(db_session, db_session.get(FantasyRound, scenario.later.id))
    assert exc.value.code == "calendar_not_found"
    db_session.rollback()
