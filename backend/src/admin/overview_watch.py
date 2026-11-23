"""«Da guardare» del Riepilogo operatore (release 1.4, decisioni di Rosario del 22/11).

Raccoglie in una sola risposta le cose che aspettano l'operatore, ognuna con il dato che serve
per la riga del Riepilogo (sito e app):

- richieste tester in attesa e segnalazioni nuove;
- job spenti ed esito dei giri finiti con errore nelle ultime 24 ore (``system_job_runs``);
- ultimo aggiornamento del listone (``listone_updates``);
- giornate in corso nelle leghe attive e prossimo blocco delle formazioni fra tutte le leghe
  (calcolato a ogni richiesta, con le stesse regole del countdown e dei promemoria);
- versione dell'app Android annunciata e quanti la hanno su quanti usano l'app (1.4, 23/11).

Solo letture, tranne i job mancanti che ``list_jobs`` aggiunge come la pagina «Job automatici».
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from admin.app_version import AppVersionStore
from admin.schemas import (
    AdminCurrentRoundsResponse,
    AdminListoneUpdateResponse,
    AdminNextLineupLockResponse,
    AdminWatchJobFailureResponse,
    AdminWatchJobResponse,
    AdminWatchResponse,
    AndroidAppVersionResponse,
)
from app_usage.service import app_usage_summary
from auth.models.tester_request import TesterAccessRequest
from auth.tester_requests import STATUS_PENDING
from database.enums import FantasyTurnStatus, LeagueState
from fantasy_lineups.kickoffs import athlete_kickoffs
from fantasy_lineups.rules import DEFAULT_LINEUP_LOCK_MARGIN_MINUTES, next_unlocked_kickoff
from fantasy_teams.models import FantasyRosterSlot, FantasyTeam
from fantasy_turns.models import FantasyRound
from feedback.models import FeedbackReport
from leagues.models.league import League
from leagues.models.league_rules import LeagueRules
from observability.logging import get_logger
from sports_data.listone.update_log import latest_listone_update
from system_jobs.runs import recent_failures
from system_jobs.service import list_jobs

logger = get_logger(__name__)

#: Errori dei job mostrati nel Riepilogo: quelli delle ultime 24 ore («stanotte»).
JOB_FAILURE_WINDOW = timedelta(hours=24)
#: Come i promemoria di blocco: un turno bloccato conta ancora finché la finestra è recente
#: (il blocco è per calciatore, le partite dopo la prima hanno ancora il loro istante).
_LOCK_LOOKBACK = timedelta(days=2)
_IN_PROGRESS = (FantasyTurnStatus.OPEN, FantasyTurnStatus.LOCKED)


def leagues_by_state(session: Session) -> dict[str, int]:
    rows = session.execute(select(League.state, func.count(League.id)).group_by(League.state))
    return {
        (state.value if isinstance(state, LeagueState) else str(state)): int(count)
        for state, count in rows
    }


def build_watch(session: Session, *, now: datetime) -> AdminWatchResponse:
    tester_pending, oldest_tester = session.execute(
        select(func.count(TesterAccessRequest.id), func.min(TesterAccessRequest.created_at)).where(
            TesterAccessRequest.status == STATUS_PENDING
        )
    ).one()
    feedback_new, latest_feedback = session.execute(
        select(func.count(FeedbackReport.id), func.max(FeedbackReport.created_at)).where(
            FeedbackReport.status == "new"
        )
    ).one()
    jobs_disabled = [
        AdminWatchJobResponse(key=job.key, title=job.title)
        for job in list_jobs(session)
        if not job.enabled
    ]
    failures_since = now - JOB_FAILURE_WINDOW
    job_failures = [
        AdminWatchJobFailureResponse(
            jobKey=view.job_key,
            title=view.title,
            failedAt=view.failed_at,
            reason=view.reason,
            failures=view.failures,
            lastOutcome=view.last_outcome,  # type: ignore[arg-type]
            lastFinishedAt=view.last_finished_at,
        )
        for view in recent_failures(session, since=failures_since)
    ]
    announced = AppVersionStore(session).get().android
    return AdminWatchResponse(
        generatedAt=now,
        testerRequestsPending=int(tester_pending or 0),
        oldestTesterRequestAt=oldest_tester,
        feedbackNew=int(feedback_new or 0),
        latestFeedbackAt=latest_feedback,
        jobsDisabled=jobs_disabled,
        jobFailuresSince=failures_since,
        jobFailures=job_failures,
        listoneLastUpdate=_listone_last_update(session),
        currentRounds=current_rounds(session, now=now),
        nextLineupLock=next_lineup_lock(session, now=now),
        androidAppVersion=announced,
        androidAppUsage=_app_usage(session, announced),
    )


def _app_usage(session: Session, announced: AndroidAppVersionResponse | None):
    """Aggiornati su chi usa l'app; un guasto qui toglie solo il conteggio, non la riga."""
    try:
        with session.begin_nested():
            return app_usage_summary(session, announced)
    except Exception:
        logger.exception("admin_watch_app_usage_failed")
        return None


def _listone_last_update(session: Session) -> AdminListoneUpdateResponse | None:
    row = latest_listone_update(session)
    if row is None:
        return None
    return AdminListoneUpdateResponse(
        updatedAt=row.created_at,
        seasonYear=row.season_year,
        kind=row.kind,  # type: ignore[arg-type]
        source=row.source,  # type: ignore[arg-type]
        authorDisplayName=row.actor_display_name,
        leagueName=row.league_name,
        added=row.added,
        removed=row.removed,
        changed=row.changed,
    )


def current_rounds(session: Session, *, now: datetime) -> AdminCurrentRoundsResponse:
    """Leghe attive con una giornata in corso: turno aperto, o bloccato con la finestra aperta."""
    active_leagues = (
        session.scalar(select(func.count(League.id)).where(League.state == LeagueState.ACTIVE)) or 0
    )
    rows = session.execute(
        select(FantasyRound.league_id, func.min(FantasyRound.number))
        .join(League, League.id == FantasyRound.league_id)
        .where(
            League.state == LeagueState.ACTIVE,
            (FantasyRound.status == FantasyTurnStatus.OPEN)
            | (
                (FantasyRound.status == FantasyTurnStatus.LOCKED)
                & (FantasyRound.window_end_at >= now)
            ),
        )
        .group_by(FantasyRound.league_id)
    ).all()
    numbers = sorted({int(number) for _league_id, number in rows})
    return AdminCurrentRoundsResponse(
        activeLeagues=int(active_leagues),
        leaguesInProgress=len(rows),
        roundNumbers=numbers,
    )


def next_lineup_lock(session: Session, *, now: datetime) -> AdminNextLineupLockResponse | None:
    """Il prossimo istante in cui si blocca almeno un calciatore in una rosa di una lega attiva.

    Stesso calcolo del countdown «Prossimo blocco» e dei promemoria di blocco
    (``next_unlocked_kickoff`` meno il margine della lega), fatto sull'unione delle rose di
    ogni lega: è il primo blocco che tocca qualcuno in quella lega.
    """
    rounds = session.execute(
        select(FantasyRound, League)
        .join(League, League.id == FantasyRound.league_id)
        .where(
            League.state == LeagueState.ACTIVE,
            FantasyRound.status.in_(_IN_PROGRESS),
            FantasyRound.window_end_at >= now - _LOCK_LOOKBACK,
        )
        .order_by(FantasyRound.window_start_at.asc())
    ).all()
    best: tuple[datetime, League, FantasyRound] | None = None
    margins: dict[UUID, int] = {}
    rosters: dict[UUID, list[UUID]] = {}
    for fantasy_round, league in rounds:
        if league.id not in rosters:
            rosters[league.id] = list(
                session.scalars(
                    select(FantasyRosterSlot.athlete_id)
                    .join(FantasyTeam, FantasyTeam.id == FantasyRosterSlot.fantasy_team_id)
                    .where(
                        FantasyTeam.league_id == league.id,
                        FantasyRosterSlot.athlete_id.is_not(None),
                    )
                    .distinct()
                ).all()
            )
        athlete_ids = rosters[league.id]
        if not athlete_ids:
            continue
        if league.id not in margins:
            margin = session.scalar(
                select(LeagueRules.lineup_lock_margin_minutes).where(
                    LeagueRules.league_id == league.id
                )
            )
            margins[league.id] = (
                margin if margin is not None else DEFAULT_LINEUP_LOCK_MARGIN_MINUTES
            )
        margin_minutes = margins[league.id]
        kickoffs = athlete_kickoffs(
            session,
            round_id=fantasy_round.id,
            season_year=league.season_year,
            athlete_ids=athlete_ids,
        )
        kickoff = next_unlocked_kickoff(
            ((ref.kickoff_at, ref.status_short, ref.lock_latched) for ref in kickoffs.values()),
            now=now,
            margin_minutes=margin_minutes,
        )
        if kickoff is None:
            continue
        lock_at = kickoff - timedelta(minutes=margin_minutes)
        if best is None or lock_at < best[0]:
            best = (lock_at, league, fantasy_round)
    if best is None:
        return None
    lock_at, league, fantasy_round = best
    return AdminNextLineupLockResponse(
        lockAt=lock_at,
        leagueId=str(league.id),
        leagueName=league.name,
        roundNumber=fantasy_round.number,
    )
