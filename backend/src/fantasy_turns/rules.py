"""European fantasy turn generation and cutoff rules (EP06-01 / EP06-07)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import TypeVar
from zoneinfo import ZoneInfo

from auth.exceptions import ValidationAuthError
from database.enums import FantasyTurnKind, FantasyTurnStatus

_T = TypeVar("_T")

DEFAULT_LEAGUE_TZ = ZoneInfo("Europe/Rome")
CANCELLED_FIXTURE_STATUSES = frozenset({"CANC"})
# Terminal statuses that never contribute a live kickoff to cutoff.
CUTOFF_EXCLUDED_STATUSES = frozenset({"CANC", "ABD", "AWD", "WO"})
POSTPONED_FIXTURE_STATUSES = frozenset({"PST"})
STARTED_FIXTURE_STATUSES = frozenset(
    {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP", "FT", "AET", "PEN"}
)
INACTIVE_FIXTURE_STATUSES = frozenset({"PST", "CANC", "ABD", "AWD", "WO"})
STANDARD_MIN_FIXTURES = 25
MIN_FIXTURES_PER_ROUND = 10
MAX_FIXTURES_PER_ROUND = 40


@dataclass(frozen=True)
class TimeWindow:
    start_at: datetime
    end_at: datetime
    kind: FantasyTurnKind
    timezone: str


@dataclass(frozen=True)
class ThresholdResult:
    eligible_count: int
    min_required: int
    ok: bool
    skip_reason: str | None


@dataclass(frozen=True)
class EligibleFixtureRef:
    fixture_id: object
    kickoff_at: datetime
    status_short: str


@dataclass(frozen=True)
class KickoffLockState:
    observed_kickoff_at: datetime | None
    lock_latched_at: datetime | None
    just_latched: bool


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def resolve_zone(tz_name: str = "Europe/Rome") -> ZoneInfo:
    return ZoneInfo(tz_name)


def weekend_window(anchor: date, *, tz_name: str = "Europe/Rome") -> TimeWindow:
    """Friday 00:00 – exclusive Tuesday 00:00 in the league timezone (Standard)."""
    tz = resolve_zone(tz_name)
    friday = _friday_for_weekend_anchor(anchor)
    start_local = datetime.combine(friday, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=4)
    return TimeWindow(
        start_at=ensure_utc(start_local),
        end_at=ensure_utc(end_local),
        kind=FantasyTurnKind.WEEKEND,
        timezone=tz_name,
    )


def midweek_window(anchor: date, *, tz_name: str = "Europe/Rome") -> TimeWindow:
    """Tuesday 00:00 – exclusive Friday 00:00 in the league timezone."""
    tz = resolve_zone(tz_name)
    tuesday = _tuesday_for_midweek_anchor(anchor)
    start_local = datetime.combine(tuesday, time.min, tzinfo=tz)
    end_local = start_local + timedelta(days=3)
    return TimeWindow(
        start_at=ensure_utc(start_local),
        end_at=ensure_utc(end_local),
        kind=FantasyTurnKind.MIDWEEK,
        timezone=tz_name,
    )


def window_for_kind(
    kind: FantasyTurnKind,
    anchor: date,
    *,
    tz_name: str = "Europe/Rome",
) -> TimeWindow:
    if kind == FantasyTurnKind.WEEKEND:
        return weekend_window(anchor, tz_name=tz_name)
    if kind == FantasyTurnKind.MIDWEEK:
        return midweek_window(anchor, tz_name=tz_name)
    raise ValidationAuthError(
        "Tipo di turno non supportato.",
        code="invalid_turn_kind",
    )


def _friday_for_weekend_anchor(anchor: date) -> date:
    # Mon=0 … Sun=6. Weekend span Fri–Mon.
    weekday = anchor.weekday()
    if weekday == 0:  # Monday → previous Friday
        return anchor - timedelta(days=3)
    if weekday >= 4:  # Fri/Sat/Sun
        return anchor - timedelta(days=weekday - 4)
    # Tue–Thu → upcoming Friday
    return anchor + timedelta(days=4 - weekday)


def _tuesday_for_midweek_anchor(anchor: date) -> date:
    weekday = anchor.weekday()
    if weekday == 1:  # Tuesday
        return anchor
    if weekday in {2, 3}:  # Wed/Thu → that week's Tuesday
        return anchor - timedelta(days=weekday - 1)
    if weekday == 0:  # Monday → next Tuesday
        return anchor + timedelta(days=1)
    # Fri–Sun → previous Tuesday of midweek just ended, or next? Use next week's Tue.
    return anchor + timedelta(days=(8 - weekday) % 7 or 7)


def is_fixture_status_eligible(status_short: str) -> bool:
    return status_short.upper() not in CANCELLED_FIXTURE_STATUSES


LIVE_MATCH_STATUSES = frozenset({"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT", "SUSP"})
FINISHED_MATCH_STATUSES = frozenset({"FT", "AET", "PEN"})


def aggregate_turn_status(
    fixtures: Sequence[tuple[str | None, datetime | None]],
) -> str:
    """Stato aggregato di un turno per la UI (§23): completed | live | scheduled | needs_update.

    Specchio Python di `aggregateTurnStatus` in `packages/contracts/src/fantasyTurns.ts`
    — stessa logica, così web/mobile e l'elenco turni lato server restano coerenti.
    """
    if not fixtures:
        return "needs_update"
    has_live = False
    has_needs_update = False
    all_terminal = True
    for status_short, kickoff_at in fixtures:
        status = (status_short or "").strip().upper()
        if status in LIVE_MATCH_STATUSES:
            has_live = True
            all_terminal = False
            continue
        if (
            status in FINISHED_MATCH_STATUSES
            or status in POSTPONED_FIXTURE_STATUSES
            or status in CUTOFF_EXCLUDED_STATUSES
        ):
            continue
        all_terminal = False
        if kickoff_at is None:
            has_needs_update = True
    if has_live:
        return "live"
    if has_needs_update:
        return "needs_update"
    if all_terminal:
        return "completed"
    return "scheduled"


def resolve_default_turn(entries: Sequence[tuple[_T, str]]) -> _T | None:
    """Turno di default da mostrare: il primo non ancora concluso, o l'ultimo.

    Specchio Python di `resolveDefaultEuropeanTurn` in
    `packages/contracts/src/fantasyTurns.ts` — stessa logica, così un
    countdown risolto lato server e la pagina Turni lato client puntano
    sempre allo stesso turno. Il chiamante passa le voci già ordinate per
    numero crescente.
    """
    for item, match_status in entries:
        if match_status != "completed":
            return item
    return entries[-1][0] if entries else None


def kickoff_in_window(kickoff_at: datetime, window: TimeWindow) -> bool:
    ko = ensure_utc(kickoff_at)
    return window.start_at <= ko < window.end_at


def evaluate_threshold(eligible_count: int, min_required: int) -> ThresholdResult:
    if min_required < MIN_FIXTURES_PER_ROUND or min_required > MAX_FIXTURES_PER_ROUND:
        raise ValidationAuthError(
            f"La soglia partite deve essere tra {MIN_FIXTURES_PER_ROUND} e "
            f"{MAX_FIXTURES_PER_ROUND}.",
            code="invalid_min_fixtures_per_round",
        )
    if eligible_count >= min_required:
        return ThresholdResult(
            eligible_count=eligible_count,
            min_required=min_required,
            ok=True,
            skip_reason=None,
        )
    return ThresholdResult(
        eligible_count=eligible_count,
        min_required=min_required,
        ok=False,
        skip_reason=(
            f"Soglia non raggiunta: {eligible_count} partite eleggibili su "
            f"{min_required} richieste."
        ),
    )


def compute_cutoff(kickoffs: Sequence[datetime]) -> datetime | None:
    """Cutoff is the earliest kickoff among included fixtures (simultaneous → same)."""
    if not kickoffs:
        return None
    return min(ensure_utc(ko) for ko in kickoffs)


def kickoff_counts_for_cutoff(
    *,
    kickoff_at: datetime | None,
    status_short: str | None,
    now: datetime,
) -> bool:
    """True when a fixture still contributes a live kickoff to the current cutoff."""
    if kickoff_at is None:
        return False
    status = (status_short or "").strip().upper()
    if status in CUTOFF_EXCLUDED_STATUSES:
        return False
    if status in POSTPONED_FIXTURE_STATUSES:
        return ensure_utc(kickoff_at) > ensure_utc(now)
    return True


def apply_cutoff_recalculation(
    *,
    previous_cutoff: datetime | None,
    candidate_cutoff: datetime | None,
    now: datetime,
) -> datetime | None:
    """Move cutoff earlier freely; never move it later after it has elapsed.

    Postponing the first kickoff *before* it starts may delay cutoff. After the
    original instant has passed, a later candidate must not reopen the window.
    """
    now_utc = ensure_utc(now)
    previous = ensure_utc(previous_cutoff) if previous_cutoff is not None else None
    candidate = ensure_utc(candidate_cutoff) if candidate_cutoff is not None else None
    if previous is not None and now_utc >= previous:
        if candidate is None or candidate > previous:
            return previous
        return candidate
    return candidate


def reconcile_fixture_kickoff_lock(
    *,
    now: datetime,
    current_kickoff_at: datetime | None,
    status_short: str | None,
    observed_kickoff_at: datetime | None,
    lock_latched_at: datetime | None,
) -> KickoffLockState:
    """Latch lock once a published kickoff elapses; later postponements cannot unlock."""
    now_utc = ensure_utc(now)
    observed = ensure_utc(observed_kickoff_at) if observed_kickoff_at is not None else None
    current = ensure_utc(current_kickoff_at) if current_kickoff_at is not None else None
    latched = ensure_utc(lock_latched_at) if lock_latched_at is not None else None
    status = (status_short or "").strip().upper()
    just_latched = False

    if latched is None:
        published_elapsed = observed is not None and now_utc >= observed
        current_elapsed = (
            current is not None and status not in INACTIVE_FIXTURE_STATUSES and now_utc >= current
        )
        started = status in STARTED_FIXTURE_STATUSES
        if published_elapsed or current_elapsed or started:
            latched = observed or current or now_utc
            just_latched = True

    new_observed = current if current is not None else observed
    return KickoffLockState(
        observed_kickoff_at=new_observed,
        lock_latched_at=latched,
        just_latched=just_latched,
    )


def derive_effective_status(
    stored: FantasyTurnStatus,
    *,
    now: datetime,
    cutoff_at: datetime | None,
) -> FantasyTurnStatus:
    if stored in {FantasyTurnStatus.SKIPPED, FantasyTurnStatus.LOCKED, FantasyTurnStatus.SCHEDULED}:
        return stored
    if stored == FantasyTurnStatus.OPEN and cutoff_at is not None:
        if ensure_utc(now) >= ensure_utc(cutoff_at):
            return FantasyTurnStatus.LOCKED
    return stored


def is_modification_allowed(
    *,
    stored: FantasyTurnStatus,
    now: datetime,
    cutoff_at: datetime | None,
) -> bool:
    effective = derive_effective_status(stored, now=now, cutoff_at=cutoff_at)
    return effective == FantasyTurnStatus.SCHEDULED


def assert_modification_allowed(
    *,
    stored: FantasyTurnStatus,
    now: datetime,
    cutoff_at: datetime | None,
) -> None:
    if is_modification_allowed(stored=stored, now=now, cutoff_at=cutoff_at):
        return
    effective = derive_effective_status(stored, now=now, cutoff_at=cutoff_at)
    if effective == FantasyTurnStatus.SKIPPED:
        raise ValidationAuthError(
            "Il turno non è stato disputato e non può essere modificato.",
            code="turn_skipped",
        )
    if effective == FantasyTurnStatus.OPEN:
        raise ValidationAuthError(
            "Il turno è già aperto: esclusione e rigenerazione non sono consentite.",
            code="turn_already_open",
        )
    raise ValidationAuthError(
        "Modifica fuori tempo: il cutoff del turno è già trascorso.",
        code="turn_modification_closed",
    )


def select_eligible_from_candidates(
    candidates: Iterable[EligibleFixtureRef],
    window: TimeWindow,
    *,
    already_assigned_ids: set[object] | None = None,
) -> list[EligibleFixtureRef]:
    assigned = already_assigned_ids or set()
    selected: list[EligibleFixtureRef] = []
    for row in candidates:
        if row.fixture_id in assigned:
            continue
        if not is_fixture_status_eligible(row.status_short):
            continue
        if not kickoff_in_window(row.kickoff_at, window):
            continue
        selected.append(row)
    selected.sort(key=lambda item: (ensure_utc(item.kickoff_at), str(item.fixture_id)))
    return selected


def _turn_specs_between(
    walk_start: date,
    walk_end: date,
    *,
    window_min_end_at: datetime,
    window_max_start_at: datetime,
    tz_name: str,
) -> list[tuple[FantasyTurnKind, date]]:
    """Unique (kind, anchor) windows overlapping [window_min_end_at, window_max_start_at).

    Shared walk used by both the "orizzonte da oggi" (`upcoming_turn_specs`)
    and "intera stagione" (`full_season_turn_specs`) enumerations, so the two
    always produce identical, chronologically-sorted window boundaries.
    """
    tz = resolve_zone(tz_name)
    specs: list[tuple[FantasyTurnKind, date]] = []
    seen: set[tuple[FantasyTurnKind, datetime, datetime]] = set()
    cursor = walk_start
    while cursor <= walk_end:
        for kind in (FantasyTurnKind.WEEKEND, FantasyTurnKind.MIDWEEK):
            window = window_for_kind(kind, cursor, tz_name=tz_name)
            key = (kind, window.start_at, window.end_at)
            if key in seen:
                continue
            if window.end_at <= window_min_end_at:
                continue
            if window.start_at >= window_max_start_at:
                continue
            seen.add(key)
            anchor = window.start_at.astimezone(tz).date()
            specs.append((kind, anchor))
        cursor += timedelta(days=1)
    specs.sort(
        key=lambda item: (
            window_for_kind(item[0], item[1], tz_name=tz_name).start_at,
            item[0].value,
        )
    )
    return specs


def upcoming_turn_specs(
    reference: date,
    *,
    horizon_days: int = 14,
    tz_name: str = "Europe/Rome",
) -> list[tuple[FantasyTurnKind, date]]:
    """Unique (kind, anchor) windows overlapping [reference, reference+horizon).

    Anchor is the local start date of the window (Friday or Tuesday).
    Windows already fully ended before ``reference`` are omitted; windows that
    start at/after the horizon end are omitted.
    """
    if horizon_days < 1:
        raise ValidationAuthError(
            "L'orizzonte di generazione deve essere almeno 1 giorno.",
            code="invalid_turn_horizon",
        )
    tz = resolve_zone(tz_name)
    ref_start = ensure_utc(datetime.combine(reference, time.min, tzinfo=tz))
    horizon_end = ensure_utc(
        datetime.combine(reference + timedelta(days=horizon_days), time.min, tzinfo=tz)
    )
    # Walk a few days before reference so in-progress midweek/weekend still appear.
    return _turn_specs_between(
        reference - timedelta(days=4),
        reference + timedelta(days=horizon_days),
        window_min_end_at=ref_start,
        window_max_start_at=horizon_end,
        tz_name=tz_name,
    )


def full_season_turn_specs(
    season_start: date,
    season_end: date,
    *,
    tz_name: str = "Europe/Rome",
) -> list[tuple[FantasyTurnKind, date]]:
    """Unique (kind, anchor) windows covering an entire season, in order.

    Used by the "Aggiorna calendario" full backfill: unlike
    `upcoming_turn_specs`, it is not anchored to "today" and does not drop
    windows that are already in the past — it must be able to (re)materialize
    the whole season regardless of when the sync actually runs.
    """
    if season_end < season_start:
        raise ValidationAuthError(
            "L'intervallo stagione non è valido.",
            code="invalid_season_range",
        )
    tz = resolve_zone(tz_name)
    range_start = ensure_utc(datetime.combine(season_start, time.min, tzinfo=tz))
    range_end = ensure_utc(
        datetime.combine(season_end + timedelta(days=1), time.min, tzinfo=tz)
    )
    return _turn_specs_between(
        season_start - timedelta(days=4),
        season_end + timedelta(days=4),
        window_min_end_at=range_start,
        window_max_start_at=range_end,
        tz_name=tz_name,
    )
