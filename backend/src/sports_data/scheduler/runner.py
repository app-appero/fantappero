"""Execute one sports polling cycle for a pre/live/post/late window (EP04-06)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import database.models  # noqa: F401 — register ORM mappers
from leagues.models.competition import Competition
from observability.logging import get_logger
from observability.metrics import Timer, get_metrics
from sports_data.catalog.models import SportSeason
from sports_data.fixtures.models import Fixture, OfficialLineup
from sports_data.fixtures.sync import (
    FixtureDetailBatch,
    FixtureSyncResult,
    sync_fixtures,
)
from sports_data.provider.client import ApiFootballClient
from sports_data.provider.constants import MVP_LEAGUE_IDS, PROVIDER_NAME
from sports_data.provider.mapping import map_fixtures
from sports_data.provider.types import ProviderEnvelope, ProviderRateLimit
from sports_data.scheduler.locks import JobLock, hold_job_lock
from sports_data.scheduler.models import SportsPollRun
from sports_data.scheduler.policy import WindowPolicy, effective_interval_seconds, policy_for
from sports_data.scheduler.quota import (
    QuotaMode,
    allow_criticality,
    max_fixtures_for_mode,
    resolve_quota_mode,
)
from sports_data.scheduler.windows import PollWindow, classify_fixture_window

logger = get_logger(__name__)

SCHEDULER_RUNS_TOTAL = "sports_scheduler_runs_total"
SCHEDULER_DURATION_SECONDS = "sports_scheduler_duration_seconds"
SCHEDULER_FIXTURES_TOTAL = "sports_scheduler_fixtures_total"
SCHEDULER_QUOTA_MODE = "sports_scheduler_quota_mode"
SCHEDULER_SKIPPED_INTERVAL_TOTAL = "sports_scheduler_skipped_interval_total"

PollStatus = str  # ok | skipped_* | degraded_ok | error


@dataclass
class PollCycleResult:
    window: PollWindow
    status: PollStatus
    quota_mode: QuotaMode
    run_id: UUID | None = None
    fixtures_considered: int = 0
    fixtures_polled: int = 0
    provider_requests: int = 0
    sync: FixtureSyncResult | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None


def select_fixtures_for_window(
    session: Session,
    window: PollWindow,
    *,
    now: datetime | None = None,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
) -> list[Fixture]:
    """Load MVP fixtures whose classified window matches ``window``."""
    clock = now or datetime.now(UTC)
    allowed = frozenset(league_ids)
    rows = session.scalars(
        select(Fixture)
        .join(SportSeason)
        .join(Competition)
        .where(Competition.provider_id.in_(allowed)),
    ).all()
    return [
        row
        for row in rows
        if classify_fixture_window(
            status_short=row.status_short,
            kickoff_at=row.kickoff_at,
            now=clock,
        )
        == window
    ]


def last_successful_run_at(session: Session, window: PollWindow) -> datetime | None:
    row = session.scalars(
        select(SportsPollRun)
        .where(
            SportsPollRun.window == window.value,
            SportsPollRun.status.in_(("ok", "degraded_ok")),
        )
        .order_by(SportsPollRun.finished_at.desc())
        .limit(1),
    ).first()
    return row.finished_at if row is not None else None


def should_skip_for_interval(
    *,
    window: PollWindow,
    mode: QuotaMode,
    last_ok_at: datetime | None,
    now: datetime | None = None,
) -> bool:
    """Skip when a prior success is still inside the (possibly degraded) interval."""
    if last_ok_at is None:
        return False
    clock = now or datetime.now(UTC)
    if last_ok_at.tzinfo is None:
        last_ok = last_ok_at.replace(tzinfo=UTC)
    else:
        last_ok = last_ok_at.astimezone(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    needed = effective_interval_seconds(window, mode)
    return (clock - last_ok).total_seconds() < needed


def run_poll_cycle(
    session: Session,
    window: PollWindow,
    *,
    lock: JobLock,
    client: ApiFootballClient | None = None,
    rate_limit: ProviderRateLimit | None = None,
    fixtures_envelopes: Sequence[ProviderEnvelope] | None = None,
    detail_batches: Sequence[FixtureDetailBatch] | None = None,
    enabled: bool = True,
    now: datetime | None = None,
    league_ids: Sequence[int] = MVP_LEAGUE_IDS,
    respect_interval: bool = True,
    fetch_from_provider: bool | None = None,
) -> PollCycleResult:
    """Run one window poll with lock, quota mode, optional offline envelopes, audit row."""
    clock = now or datetime.now(UTC)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=UTC)
    policy = policy_for(window)
    metrics = get_metrics()
    labels = {"provider": PROVIDER_NAME, "window": window.value}

    if not enabled:
        result = PollCycleResult(
            window=window,
            status="skipped_disabled",
            quota_mode=QuotaMode.OK,
            details={"reason": "scheduler_disabled"},
        )
        _finalize_run(session, result, lock_token=None, started_at=clock, finished_at=clock)
        metrics.incr(SCHEDULER_RUNS_TOTAL, labels={**labels, "status": result.status})
        logger.info(
            "sports_scheduler_skipped",
            extra={"provider": PROVIDER_NAME, "window": window.value, "reason": "disabled"},
        )
        return result

    with hold_job_lock(lock, window.value, ttl_seconds=policy.lock_ttl_seconds) as token:
        if token is None:
            result = PollCycleResult(
                window=window,
                status="skipped_lock",
                quota_mode=QuotaMode.OK,
                details={"reason": "lock_busy"},
            )
            _finalize_run(session, result, lock_token=None, started_at=clock, finished_at=clock)
            metrics.incr(SCHEDULER_RUNS_TOTAL, labels={**labels, "status": result.status})
            return result

        mode = resolve_quota_mode(rate_limit)
        if client is not None and rate_limit is None and fetch_from_provider is not False:
            # Probe /status once to refresh quota headers when unknown.
            try:
                status_env = client.get("/status", fetch_all_pages=False)
                mode = resolve_quota_mode(status_env.rate_limit)
                rate_limit = status_env.rate_limit
            except Exception:  # noqa: BLE001 — degrade observability, keep last mode
                logger.warning(
                    "sports_scheduler_status_probe_failed",
                    extra={"provider": PROVIDER_NAME, "window": window.value},
                )

        metrics.set_gauge(
            SCHEDULER_QUOTA_MODE,
            float(_quota_mode_rank(mode)),
            labels={"provider": PROVIDER_NAME},
        )

        if respect_interval and should_skip_for_interval(
            window=window,
            mode=mode,
            last_ok_at=last_successful_run_at(session, window),
            now=clock,
        ):
            metrics.incr(
                SCHEDULER_SKIPPED_INTERVAL_TOTAL,
                labels={**labels, "quota_mode": mode.value},
            )
            result = PollCycleResult(
                window=window,
                status="skipped_interval",
                quota_mode=mode,
                details={
                    "reason": "interval_not_elapsed",
                    "effective_interval_seconds": effective_interval_seconds(window, mode),
                },
            )
            _finalize_run(session, result, lock_token=token, started_at=clock, finished_at=clock)
            metrics.incr(SCHEDULER_RUNS_TOTAL, labels={**labels, "status": result.status})
            logger.info(
                "sports_scheduler_skipped",
                extra={
                    "provider": PROVIDER_NAME,
                    "window": window.value,
                    "reason": "interval",
                    "quota_mode": mode.value,
                },
            )
            return result

        if mode == QuotaMode.CRITICAL_ONLY and window == PollWindow.PRE_MATCH:
            # Pre-match is not critical — suspend under critical_only (plan §5).
            result = PollCycleResult(
                window=window,
                status="skipped_quota",
                quota_mode=mode,
                details={"reason": "critical_only_suspends_pre_match"},
            )
            _finalize_run(session, result, lock_token=token, started_at=clock, finished_at=clock)
            metrics.incr(SCHEDULER_RUNS_TOTAL, labels={**labels, "status": result.status})
            logger.warning(
                "sports_scheduler_degraded",
                extra={
                    "provider": PROVIDER_NAME,
                    "window": window.value,
                    "quota_mode": mode.value,
                    "action": "skip_pre_match",
                },
            )
            return result

        candidates = select_fixtures_for_window(session, window, now=clock, league_ids=league_ids)
        fixture_cap = max_fixtures_for_mode(policy.max_fixtures_per_run, mode)
        if fixture_cap is not None:
            candidates = candidates[:fixture_cap]

        do_fetch = fetch_from_provider if fetch_from_provider is not None else client is not None
        provider_requests = 0
        sync_result: FixtureSyncResult | None = None
        status: PollStatus = "ok"
        error_code: str | None = None
        details: dict[str, Any] = {"quota_mode": mode.value}

        try:
            with Timer(metrics, SCHEDULER_DURATION_SECONDS, labels=labels):
                if fixtures_envelopes is not None or detail_batches is not None:
                    sync_result = sync_fixtures(
                        session,
                        fixtures_envelopes=fixtures_envelopes or (),
                        detail_batches=detail_batches or (),
                        league_ids=league_ids,
                    )
                    provider_requests = len(fixtures_envelopes or ()) + sum(
                        _detail_request_count(b) for b in (detail_batches or ())
                    )
                elif do_fetch and client is not None:
                    sync_result, provider_requests = _fetch_and_sync(
                        session,
                        client,
                        window=window,
                        policy=policy,
                        mode=mode,
                        candidates=candidates,
                        league_ids=league_ids,
                        clock=clock,
                    )
                else:
                    details["reason"] = "no_provider_or_envelopes"
                    # Still succeed as a dry observation of candidates.
                    sync_result = FixtureSyncResult()

            if mode in (QuotaMode.WARN, QuotaMode.DEGRADE, QuotaMode.CRITICAL_ONLY):
                status = "degraded_ok"
                details["degraded"] = True
                logger.warning(
                    "sports_scheduler_degraded",
                    extra={
                        "provider": PROVIDER_NAME,
                        "window": window.value,
                        "quota_mode": mode.value,
                        "fixtures_considered": len(candidates),
                    },
                )
        except Exception as exc:
            status = "error"
            error_code = type(exc).__name__
            details["error_type"] = error_code
            logger.exception(
                "sports_scheduler_failed",
                extra={"provider": PROVIDER_NAME, "window": window.value, "quota_mode": mode.value},
            )
            finished = datetime.now(UTC)
            result = PollCycleResult(
                window=window,
                status=status,
                quota_mode=mode,
                fixtures_considered=len(candidates),
                fixtures_polled=0,
                provider_requests=provider_requests,
                sync=sync_result,
                details=details,
                error_code=error_code,
            )
            _finalize_run(session, result, lock_token=token, started_at=clock, finished_at=finished)
            metrics.incr(SCHEDULER_RUNS_TOTAL, labels={**labels, "status": status})
            raise

        fixtures_polled = len(candidates)
        if sync_result is not None:
            details["sync"] = {
                "fixtures_created": sync_result.counters.fixtures_created,
                "fixtures_updated": sync_result.counters.fixtures_updated,
                "events_created": sync_result.counters.events_created,
                "events_corrected": sync_result.counters.events_corrected,
                "stats_created": sync_result.counters.stats_created,
            }

        finished = datetime.now(UTC)
        result = PollCycleResult(
            window=window,
            status=status,
            quota_mode=mode,
            fixtures_considered=len(candidates),
            fixtures_polled=fixtures_polled,
            provider_requests=provider_requests,
            sync=sync_result,
            details=details,
        )
        _finalize_run(session, result, lock_token=token, started_at=clock, finished_at=finished)
        metrics.incr(SCHEDULER_RUNS_TOTAL, labels={**labels, "status": status})
        metrics.incr(
            SCHEDULER_FIXTURES_TOTAL,
            labels={**labels, "result": "considered"},
            amount=float(len(candidates)),
        )
        metrics.incr(
            SCHEDULER_FIXTURES_TOTAL,
            labels={**labels, "result": "polled"},
            amount=float(fixtures_polled),
        )
        logger.info(
            "sports_scheduler_ok",
            extra={
                "provider": PROVIDER_NAME,
                "window": window.value,
                "quota_mode": mode.value,
                "status": status,
                "fixtures_considered": len(candidates),
                "fixtures_polled": fixtures_polled,
                "provider_requests": provider_requests,
            },
        )
        return result


def _fetch_and_sync(
    session: Session,
    client: ApiFootballClient,
    *,
    window: PollWindow,
    policy: WindowPolicy,
    mode: QuotaMode,
    candidates: list[Fixture],
    league_ids: Sequence[int],
    clock: datetime,
) -> tuple[FixtureSyncResult, int]:
    requests = 0
    fixtures_envelopes: list[ProviderEnvelope] = []
    detail_batches: list[FixtureDetailBatch] = []

    if policy.fetch_live_batch and allow_criticality(policy.fixtures_criticality, mode):
        envelope = client.get("/fixtures", {"live": "all"})
        requests += 1
        fixtures_envelopes.append(envelope)
        # Prefer freshly mapped live fixtures that belong to MVP leagues.
        live_mapped = [
            m for m in map_fixtures(envelope) if m.competition_provider_id in frozenset(league_ids)
        ]
        # Merge candidate provider ids with live batch.
        live_ids = {m.provider_id for m in live_mapped}
        candidate_ids = {f.provider_id for f in candidates}
        target_ids = list(live_ids | candidate_ids)
    elif window == PollWindow.PRE_MATCH and allow_criticality(policy.fixtures_criticality, mode):
        fixtures_envelopes, extra = _fetch_pre_calendars(
            session,
            client,
            league_ids=league_ids,
            clock=clock,
        )
        requests += extra
        target_ids = [f.provider_id for f in candidates]
    else:
        target_ids = [f.provider_id for f in candidates]
        if allow_criticality(policy.fixtures_criticality, mode) and target_ids:
            # Refresh status for known fixtures (no multi-id batch on provider).
            # Prefer league season calendar refresh for post/late when candidates exist.
            for league_id in league_ids:
                season = _current_season_year(session, league_id)
                if season is None:
                    continue
                env = client.get("/fixtures", {"league": league_id, "season": season})
                requests += 1
                fixtures_envelopes.append(env)
                break  # one calendar refresh is enough to update statuses; details follow

    cap = max_fixtures_for_mode(policy.max_fixtures_per_run, mode)
    if cap is not None:
        target_ids = target_ids[:cap]

    want_events = policy.fetch_events and allow_criticality(policy.events_criticality, mode)
    want_lineups = policy.fetch_lineups and allow_criticality(policy.lineups_criticality, mode)
    want_players = policy.fetch_players and allow_criticality(policy.players_criticality, mode)

    if mode == QuotaMode.CRITICAL_ONLY:
        # Plan: only status batch + events/players for live / incomplete post.
        want_lineups = False
        if window == PollWindow.LATE_CORRECTIONS:
            want_events = True
            want_players = True

    fixtures_with_both_lineups: set[int] = set()
    if want_lineups and target_ids:
        # Non richiamare /fixtures/lineups per una fixture di cui abbiamo già
        # entrambe le formazioni ufficiali (casa+ospite): la lineup non
        # cambia una volta pubblicata, è solo spreco di quota provider.
        fixtures_with_both_lineups = set(
            session.execute(
                select(Fixture.provider_id)
                .join(OfficialLineup, OfficialLineup.fixture_id == Fixture.id)
                .where(Fixture.provider_id.in_(target_ids))
                .group_by(Fixture.provider_id)
                .having(func.count(OfficialLineup.id) >= 2)
            )
            .scalars()
            .all()
        )

    for fixture_id in target_ids:
        events_env = None
        lineups_env = None
        players_env = None
        if want_events:
            events_env = client.get("/fixtures/events", {"fixture": fixture_id})
            requests += 1
        if want_lineups and fixture_id not in fixtures_with_both_lineups:
            lineups_env = client.get("/fixtures/lineups", {"fixture": fixture_id})
            requests += 1
        if want_players:
            players_env = client.get("/fixtures/players", {"fixture": fixture_id})
            requests += 1
        if events_env is not None or lineups_env is not None or players_env is not None:
            detail_batches.append(
                FixtureDetailBatch(
                    fixture_provider_id=fixture_id,
                    events_envelope=events_env,
                    lineups_envelope=lineups_env,
                    players_envelope=players_env,
                ),
            )

    result = sync_fixtures(
        session,
        fixtures_envelopes=fixtures_envelopes,
        detail_batches=detail_batches,
        league_ids=league_ids,
    )
    return result, requests


def _fetch_pre_calendars(
    session: Session,
    client: ApiFootballClient,
    *,
    league_ids: Sequence[int],
    clock: datetime,
) -> tuple[list[ProviderEnvelope], int]:
    envelopes: list[ProviderEnvelope] = []
    requests = 0
    days = (clock.date(), (clock + timedelta(days=1)).date())
    for league_id in league_ids:
        season = _current_season_year(session, league_id)
        if season is None:
            continue
        for day in days:
            env = client.get(
                "/fixtures",
                {"league": league_id, "season": season, "date": day.isoformat()},
            )
            requests += 1
            envelopes.append(env)
    return envelopes, requests


def _current_season_year(session: Session, league_provider_id: int) -> int | None:
    row = session.scalars(
        select(SportSeason)
        .join(Competition)
        .where(
            Competition.provider_id == league_provider_id,
            SportSeason.is_current.is_(True),
        )
        .limit(1),
    ).first()
    return row.year if row is not None else None


def _detail_request_count(batch: FixtureDetailBatch) -> int:
    return sum(
        1
        for env in (batch.events_envelope, batch.lineups_envelope, batch.players_envelope)
        if env is not None
    )


def _quota_mode_rank(mode: QuotaMode) -> int:
    return {
        QuotaMode.OK: 0,
        QuotaMode.WARN: 1,
        QuotaMode.DEGRADE: 2,
        QuotaMode.CRITICAL_ONLY: 3,
    }[mode]


def _record_run(
    session: Session,
    result: PollCycleResult,
    *,
    lock_token: str | None,
    started_at: datetime,
    finished_at: datetime,
) -> SportsPollRun:
    run = SportsPollRun(
        window=result.window.value,
        quota_mode=result.quota_mode.value,
        status=result.status,
        lock_token=lock_token,
        fixtures_considered=result.fixtures_considered,
        fixtures_polled=result.fixtures_polled,
        provider_requests=result.provider_requests,
        error_code=result.error_code,
        error_message=None,
        details=dict(result.details),
        started_at=started_at,
        finished_at=finished_at,
    )
    session.add(run)
    session.flush()
    return run


def _finalize_run(
    session: Session,
    result: PollCycleResult,
    *,
    lock_token: str | None,
    started_at: datetime,
    finished_at: datetime,
) -> PollCycleResult:
    run = _record_run(
        session,
        result,
        lock_token=lock_token,
        started_at=started_at,
        finished_at=finished_at,
    )
    result.run_id = run.id
    return result
