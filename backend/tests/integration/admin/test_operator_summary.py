"""Riepilogo del pannello operatore, «Da guardare» (release 1.4, decisioni di Rosario del 22/11).

- esito di ogni giro dei job periodici (bene o male e motivo), scritto dal worker;
- ultimo aggiornamento del listone (data, autore, quanti entrati/usciti/cambiati), per sempre;
- prossimo blocco delle formazioni fra tutte le leghe attive;
- tutto in ``GET /admin/overview``, solo per l'operatore.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from tests.integration.database.helpers import create_engine_for_url

from admin.schemas import AdminListoneRefreshCounters, AdminListoneRefreshResultResponse
from auth.models.tester_request import TesterAccessRequest as AccessRequest
from auth.models.user import User
from database.enums import (
    FantasyTurnKind,
    FantasyTurnStatus,
    LeagueMemberRole,
    LeagueState,
    PlatformRole,
)
from database.session import create_session_factory
from fantasy_lineups.kickoffs import KickoffRef
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound
from feedback.models import FeedbackReport
from leagues.models.league import League
from leagues.models.league_membership import LeagueMembership
from leagues.models.league_rules import LeagueRules
from leagues.schemas import LeagueListoneRefreshCounters, LeagueListoneRefreshResponse
from mail.capture import get_captured_emails
from sports_data.listone.update_models import ListoneUpdate
from sports_data.roster.models import Athlete
from system_jobs.models import SystemJob, SystemJobRun
from system_jobs.runs import (
    FAILED_RUNS_MAX_AGE,
    KEEP_RUNS_PER_JOB,
    OUTCOME_FAILED,
    OUTCOME_OK,
    record_run,
)

BROADCAST_JOB = "notifications-broadcast-dispatch"
PASSWORD = "Password123!"


@pytest.fixture
def db_session(db_url: str, migrated_engine: object) -> Session:
    engine = create_engine_for_url(db_url)
    session = create_session_factory(engine)()
    try:
        yield session
    finally:
        session.rollback()
        session.execute(delete(SystemJobRun))
        session.execute(delete(SystemJob).where(SystemJob.key == BROADCAST_JOB))
        session.execute(delete(ListoneUpdate))
        session.commit()
        session.close()
        engine.dispose()


def _login(client: TestClient, db_session: Session, email: str, *, operator: bool = False):
    client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "displayName": email.split("@")[0]},
    )
    emails = get_captured_emails()
    if emails:
        match = re.search(r"token=([A-Za-z0-9_-]+)", emails[-1].message.text_body)
        if match:
            client.post("/auth/verify-email", json={"token": match.group(1)})
    login = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    user_id = UUID(login.json()["user"]["id"])
    if operator:
        user = db_session.get(User, user_id)
        assert user is not None
        user.platform_role = PlatformRole.OPERATOR
        db_session.commit()
    return {"Authorization": f"Bearer {login.json()['accessToken']}"}, user_id


def _set_job(session: Session, key: str, *, enabled: bool) -> None:
    row = session.get(SystemJob, key)
    if row is None:
        session.add(SystemJob(key=key, enabled=enabled, interval_seconds=60))
    else:
        row.enabled = enabled
    session.commit()


def _runs(session: Session, key: str) -> list[SystemJobRun]:
    session.expire_all()
    return list(
        session.scalars(
            select(SystemJobRun)
            .where(SystemJobRun.job_key == key)
            .order_by(SystemJobRun.started_at.asc())
        ).all()
    )


# --- esito dei giri dei job -----------------------------------------------------------------


def test_a_successful_run_is_recorded_ok(db_session: Session) -> None:
    from notifications.tasks import dispatch_broadcasts_task

    _set_job(db_session, BROADCAST_JOB, enabled=True)
    result = dispatch_broadcasts_task.apply()
    assert result.successful()

    runs = _runs(db_session, BROADCAST_JOB)
    assert len(runs) == 1
    run = runs[0]
    assert run.outcome == OUTCOME_OK
    assert run.reason is None
    assert run.task_id == result.id
    assert run.finished_at >= run.started_at
    assert run.duration_ms is not None and run.duration_ms >= 0


def test_a_failed_run_is_recorded_with_its_reason(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from notifications.tasks import dispatch_broadcasts_task

    def broken(*_args: object, **_kwargs: object) -> int:
        raise RuntimeError("database del fornitore non raggiungibile")

    monkeypatch.setattr("notifications.broadcast_service.dispatch_due", broken)
    _set_job(db_session, BROADCAST_JOB, enabled=True)

    result = dispatch_broadcasts_task.apply()
    assert result.failed()

    runs = _runs(db_session, BROADCAST_JOB)
    assert [run.outcome for run in runs] == [OUTCOME_FAILED]
    assert runs[0].reason == "RuntimeError: database del fornitore non raggiungibile"


def test_a_run_skipped_because_the_job_is_off_is_not_recorded(db_session: Session) -> None:
    from notifications.tasks import dispatch_broadcasts_task

    _set_job(db_session, BROADCAST_JOB, enabled=False)
    assert dispatch_broadcasts_task.apply().successful()
    assert _runs(db_session, BROADCAST_JOB) == []


def test_the_table_stays_bounded(db_session: Session) -> None:
    now = datetime.now(UTC)
    old_failure_id = record_run(
        db_session,
        job_key=BROADCAST_JOB,
        outcome=OUTCOME_FAILED,
        reason="vecchio",
        started_at=now - FAILED_RUNS_MAX_AGE - timedelta(days=1),
        finished_at=now - FAILED_RUNS_MAX_AGE - timedelta(days=1),
    ).id
    recent_failure_id = record_run(
        db_session,
        job_key=BROADCAST_JOB,
        outcome=OUTCOME_FAILED,
        reason="stanotte",
        started_at=now - timedelta(hours=3),
        finished_at=now - timedelta(hours=3),
    ).id
    for index in range(KEEP_RUNS_PER_JOB + 10):
        moment = now - timedelta(minutes=KEEP_RUNS_PER_JOB + 10 - index)
        record_run(
            db_session,
            job_key=BROADCAST_JOB,
            outcome=OUTCOME_OK,
            started_at=moment,
            finished_at=moment,
        )
    db_session.commit()

    runs = _runs(db_session, BROADCAST_JOB)
    ok_runs = [run for run in runs if run.outcome == OUTCOME_OK]
    failed_ids = {run.id for run in runs if run.outcome == OUTCOME_FAILED}
    assert len(ok_runs) == KEEP_RUNS_PER_JOB
    # Restano i giri più recenti; l'errore della notte resta, quello di oltre 30 giorni no.
    assert min(run.started_at for run in ok_runs) == now - timedelta(minutes=KEEP_RUNS_PER_JOB)
    assert recent_failure_id in failed_ids
    assert old_failure_id not in failed_ids


# --- ultimo aggiornamento del listone -------------------------------------------------------


def _operator_user(session: Session, name: str) -> User:
    user = User(
        email=f"listone-{uuid4()}@example.com",
        password_hash="x",
        platform_role=PlatformRole.OPERATOR,
        email_verified_at=datetime.now(UTC),
    )
    session.add(user)
    session.flush()
    from auth.models.user_profile import UserProfile

    session.add(UserProfile(user_id=user.id, display_name=name))
    session.commit()
    return user


def test_operator_listone_refresh_is_saved_with_author_and_summary(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import admin.listone_tasks as tasks

    operator = _operator_user(db_session, "Rosario")
    counters = AdminListoneRefreshCounters(
        athletesCreated=4,
        athletesUpdated=10,
        membershipsCreated=4,
        membershipsUpdated=2,
        transfersCreated=1,
        listoneCreated=3,
        listoneUpdated=12,
        listoneUnchanged=500,
        listoneSkippedUnmapped=0,
        listoneRemoved=2,
        catalogSynced=True,
    )
    monkeypatch.setattr(
        tasks,
        "refresh_platform_listone",
        lambda _session, **_kwargs: AdminListoneRefreshResultResponse(
            seasonYear=2026,
            mappingVersion="v1",
            refreshedAt=datetime.now(UTC),
            message="Listone aggiornato dal provider sportivo.",
            counters=counters,
        ),
    )

    outcome = tasks.refresh_platform_listone_task(
        job_id=str(uuid4()), season_year=2026, actor_id=str(operator.id)
    )
    assert outcome["status"] == "completed"

    db_session.expire_all()
    row = db_session.scalars(select(ListoneUpdate)).one()
    assert (row.kind, row.source, row.season_year) == ("refresh", "operator", 2026)
    assert row.actor_id == operator.id
    assert row.actor_display_name == "Rosario"
    assert (row.added, row.removed, row.changed) == (3, 2, 12)
    assert row.created_at is not None


def test_a_failed_listone_refresh_leaves_no_record(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import admin.listone_tasks as tasks
    from auth.exceptions import ValidationAuthError

    def failing(*_args: object, **_kwargs: object) -> None:
        raise ValidationAuthError("Troppe richieste.", code="provider_rate_limited")

    monkeypatch.setattr(tasks, "refresh_platform_listone", failing)
    outcome = tasks.refresh_platform_listone_task(
        job_id=str(uuid4()), season_year=2026, actor_id=str(uuid4())
    )
    assert outcome == {"status": "failed", "code": "provider_rate_limited"}
    assert db_session.scalar(select(func.count(ListoneUpdate.id))) == 0


def test_league_listone_refresh_is_saved_with_the_league(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import leagues.listone_tasks as tasks
    from leagues.listone_service import LeagueListoneService

    owner = _operator_user(db_session, "Marco")
    league = League(name="Lega del Lunedì", season_year=2026, state=LeagueState.AUCTION)
    db_session.add(league)
    db_session.commit()

    def fake_refresh(_self: object, _access: object, **_kwargs: object):
        return LeagueListoneRefreshResponse(
            seasonYear=2026,
            mappingVersion="v1",
            refreshedAt=datetime.now(UTC),
            message="ok",
            counters=LeagueListoneRefreshCounters(
                athletesCreated=0,
                athletesUpdated=0,
                membershipsCreated=0,
                membershipsUpdated=0,
                transfersCreated=0,
                listoneCreated=1,
                listoneUpdated=0,
                listoneUnchanged=10,
                listoneSkippedUnmapped=0,
                listoneRemoved=0,
                catalogSynced=True,
            ),
        )

    monkeypatch.setattr(LeagueListoneService, "refresh_from_provider", fake_refresh)
    try:
        outcome = tasks.refresh_league_listone_task(
            job_id=str(uuid4()), league_id=str(league.id), actor_id=str(owner.id)
        )
        assert outcome["status"] == "completed"
        db_session.expire_all()
        row = db_session.scalars(select(ListoneUpdate)).one()
        assert (row.source, row.league_id, row.league_name) == ("league", league.id, league.name)
        assert row.actor_display_name == "Marco"
        assert (row.added, row.removed, row.changed) == (1, 0, 0)
    finally:
        db_session.execute(delete(ListoneUpdate))
        db_session.execute(delete(League).where(League.id == league.id))
        db_session.commit()


# --- prossimo blocco delle formazioni fra tutte le leghe ------------------------------------


def _league_with_round(
    session: Session,
    *,
    name: str,
    state: LeagueState,
    status: FantasyTurnStatus,
    number: int,
    window_end_at: datetime,
    margin_minutes: int | None = None,
) -> tuple[League, FantasyRound]:
    now = datetime.now(UTC)
    league = League(name=name, season_year=2026, state=state)
    session.add(league)
    session.flush()
    rules = LeagueRules(league_id=league.id)
    if margin_minutes is not None:
        rules.lineup_lock_margin_minutes = margin_minutes
    session.add(rules)
    owner = User(
        email=f"lock-{uuid4()}@example.com",
        password_hash="x",
        platform_role=PlatformRole.USER,
        email_verified_at=now,
    )
    session.add(owner)
    session.flush()
    membership = LeagueMembership(
        league_id=league.id, user_id=owner.id, role=LeagueMemberRole.OWNER
    )
    session.add(membership)
    session.flush()
    team = FantasyTeam(league_id=league.id, membership_id=membership.id, name=f"{name} FC")
    session.add(team)
    session.flush()
    athlete = Athlete(provider_id=9_700_000 + number * 10 + len(name), canonical_name=f"{name} 9")
    session.add(athlete)
    session.flush()
    session.add(
        FantasyRosterSlot(
            fantasy_team_id=team.id, league_id=league.id, slot_index=0, athlete_id=athlete.id
        )
    )
    fantasy_round = FantasyRound(
        league_id=league.id,
        number=number,
        kind=FantasyTurnKind.WEEKEND,
        window_start_at=window_end_at - timedelta(days=3),
        window_end_at=window_end_at,
        status=status,
        generated_at=now,
    )
    session.add(fantasy_round)
    session.commit()
    return league, fantasy_round


def test_next_lock_is_the_earliest_among_active_leagues(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from admin.overview_watch import current_rounds, next_lineup_lock

    now = datetime.now(UTC).replace(microsecond=0)
    in_three_days = now + timedelta(days=3)
    late, late_round = _league_with_round(
        db_session,
        name="Lega Tardi",
        state=LeagueState.ACTIVE,
        status=FantasyTurnStatus.OPEN,
        number=12,
        window_end_at=in_three_days,
    )
    soon, soon_round = _league_with_round(
        db_session,
        name="Lega Presto",
        state=LeagueState.ACTIVE,
        status=FantasyTurnStatus.LOCKED,
        number=12,
        window_end_at=in_three_days,
        margin_minutes=30,
    )
    draft, draft_round = _league_with_round(
        db_session,
        name="Lega in bozza",
        state=LeagueState.DRAFT,
        status=FantasyTurnStatus.OPEN,
        number=1,
        window_end_at=in_three_days,
    )
    done, done_round = _league_with_round(
        db_session,
        name="Lega finita",
        state=LeagueState.ACTIVE,
        status=FantasyTurnStatus.LOCKED,
        number=11,
        window_end_at=now - timedelta(days=5),
    )
    kickoffs = {
        late_round.id: now + timedelta(hours=5),
        soon_round.id: now + timedelta(hours=2),
        # Leghe non attive o turni vecchi: non contano anche se più vicini.
        draft_round.id: now + timedelta(minutes=50),
        done_round.id: now + timedelta(minutes=40),
    }

    def fake_kickoffs(_session: Session, *, round_id: UUID, athlete_ids: list[UUID], **_kw):
        return {athlete_ids[0]: KickoffRef(kickoff_at=kickoffs[round_id], status_short="NS")}

    monkeypatch.setattr("admin.overview_watch.athlete_kickoffs", fake_kickoffs)
    try:
        lock = next_lineup_lock(db_session, now=now)
        assert lock is not None
        assert lock.league_id == str(soon.id)
        assert lock.league_name == "Lega Presto"
        assert lock.round_number == 12
        # Il blocco arriva prima del calcio d'inizio, del margine della lega (30 minuti).
        assert lock.lock_at == now + timedelta(hours=2) - timedelta(minutes=30)

        rounds = current_rounds(db_session, now=now)
        assert rounds.active_leagues == 3
        assert rounds.leagues_in_progress == 2
        assert rounds.round_numbers == [12]

        # Calcio d'inizio già passato (oltre il margine): conta il blocco successivo.
        kickoffs[soon_round.id] = now + timedelta(minutes=10)
        later = next_lineup_lock(db_session, now=now)
        assert later is not None and later.league_name == "Lega Tardi"
    finally:
        db_session.rollback()
        for league in (late, soon, draft, done):
            db_session.execute(delete(League).where(League.id == league.id))
        db_session.commit()


# --- endpoint ------------------------------------------------------------------------------


def test_overview_is_for_operators_only(client: TestClient, db_session: Session) -> None:
    member, _ = _login(client, db_session, "riepilogo-member@example.com")
    assert client.get("/admin/overview", headers=member).status_code == 403
    assert client.get("/admin/overview").status_code == 401


def test_overview_returns_what_the_summary_needs(client: TestClient, db_session: Session) -> None:
    operator, operator_id = _login(
        client, db_session, "riepilogo-operator@example.com", operator=True
    )
    now = datetime.now(UTC)
    tester = AccessRequest(
        email=f"tester-{uuid4()}@example.com",
        first_name="Anna",
        last_name="Rossi",
        status="pending",
        consent_at=now,
    )
    report = FeedbackReport(user_id=operator_id, category="bug", message="Non salva", status="new")
    db_session.add_all([tester, report])
    _set_job(db_session, BROADCAST_JOB, enabled=False)
    record_run(
        db_session,
        job_key="sports-poll-late",
        outcome=OUTCOME_FAILED,
        reason="Fornitore sportivo: troppe richieste, limite raggiunto (ProviderRateLimitError).",
        started_at=now - timedelta(hours=5),
        finished_at=now - timedelta(hours=5),
    )
    record_run(
        db_session,
        job_key="sports-poll-late",
        outcome=OUTCOME_OK,
        started_at=now - timedelta(hours=4),
        finished_at=now - timedelta(hours=4),
    )
    record_run(
        db_session,
        job_key="sports-poll-pre",
        outcome=OUTCOME_FAILED,
        reason="vecchio di due giorni",
        started_at=now - timedelta(days=2),
        finished_at=now - timedelta(days=2),
    )
    db_session.add(
        ListoneUpdate(
            season_year=2026,
            kind="refresh",
            source="operator",
            actor_id=operator_id,
            actor_display_name="Rosario",
            added=3,
            removed=1,
            changed=7,
        )
    )
    db_session.commit()
    try:
        response = client.get("/admin/overview", headers=operator)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["usersCount"] >= 1
        assert isinstance(body["leaguesByState"], dict)
        watch = body["watch"]
        assert watch["testerRequestsPending"] >= 1
        assert watch["oldestTesterRequestAt"] is not None
        assert watch["feedbackNew"] >= 1
        assert {"key": BROADCAST_JOB, "title": "Avvisi programmati"} in watch["jobsDisabled"]
        failures = watch["jobFailures"]
        assert [failure["jobKey"] for failure in failures] == ["sports-poll-late"]
        assert failures[0]["title"] == "Correzioni tardive"
        assert failures[0]["reason"].startswith("Fornitore sportivo: troppe richieste")
        assert failures[0]["failures"] == 1
        assert failures[0]["lastOutcome"] == "ok"
        listone = watch["listoneLastUpdate"]
        assert listone["authorDisplayName"] == "Rosario"
        assert (listone["added"], listone["removed"], listone["changed"]) == (3, 1, 7)
        assert listone["source"] == "operator"
        assert set(watch["currentRounds"]) == {
            "activeLeagues",
            "leaguesInProgress",
            "roundNumbers",
        }
        assert "nextLineupLock" in watch
        assert watch["androidAppVersion"] is None
    finally:
        db_session.rollback()
        db_session.execute(delete(AccessRequest).where(AccessRequest.id == tester.id))
        db_session.execute(delete(FeedbackReport).where(FeedbackReport.id == report.id))
        db_session.commit()
