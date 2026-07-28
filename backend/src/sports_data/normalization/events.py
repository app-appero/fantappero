"""Normalize fixtures/events + fixtures/players into internal scoring events."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from sports_data.normalization.keys import event_provider_key, stats_provider_key
from sports_data.normalization.types import (
    AnomalyCode,
    EventStatus,
    NormalizationResult,
    NormalizedScoringEvent,
    ScoringEventKind,
)


@dataclass(frozen=True)
class _MissCandidate:
    player_id: int | None
    team_id: int | None
    minute_elapsed: int | None
    minute_extra: int | None
    sources: tuple[str, ...]
    raw_type: str | None
    raw_detail: str | None
    key_seed: str
    from_events: bool


@dataclass(frozen=True)
class _SaveCandidate:
    player_id: int | None
    team_id: int | None
    ordinal: int
    sources: tuple[str, ...] = ("players",)


def normalize_scoring_events(
    *,
    fixture_id: int,
    events_payload: Mapping[str, Any] | None,
    players_payload: Mapping[str, Any] | None,
) -> NormalizationResult:
    """Produce deterministic internal scoring events for one fixture.

    Does not apply fantavoto points. Contradictions and insufficient data are
    surfaced via EventStatus and AnomalyCode — never silently merged away.
    """
    raw_events = _response_list(events_payload)
    player_rows = list(_iter_player_rows(players_payload))

    out: list[NormalizedScoringEvent] = []
    fixture_anomalies: list[AnomalyCode] = []
    fixture_notes: list[str] = []

    event_goal_count = 0
    event_assist_count = 0
    event_penalty_scored = 0
    miss_from_events: list[_MissCandidate] = []

    for raw in raw_events:
        type_ = raw.get("type")
        detail = raw.get("detail")
        if type_ != "Goal":
            continue

        player = raw.get("player") or {}
        assist = raw.get("assist") or {}
        team = raw.get("team") or {}
        time_ = raw.get("time") or {}
        player_id = player.get("id")
        assist_id = assist.get("id")
        team_id = team.get("id")
        elapsed = time_.get("elapsed")
        extra = time_.get("extra")

        if detail == "Normal Goal":
            event_goal_count += 1
            status, codes = _require_player(player_id)
            out.append(
                NormalizedScoringEvent(
                    provider_event_key=event_provider_key(
                        fixture_id=fixture_id,
                        elapsed=elapsed,
                        extra=extra,
                        type_=type_,
                        detail=detail,
                        player_id=player_id,
                        assist_id=assist_id,
                        role="goal",
                    ),
                    fixture_id=fixture_id,
                    kind=ScoringEventKind.GOAL,
                    status=status,
                    player_id=player_id,
                    team_id=team_id,
                    related_player_id=assist_id,
                    minute_elapsed=elapsed,
                    minute_extra=extra,
                    sources=("events",),
                    anomaly_codes=codes,
                    raw_type=type_,
                    raw_detail=detail,
                )
            )
            if assist_id:
                event_assist_count += 1
                out.append(
                    NormalizedScoringEvent(
                        provider_event_key=event_provider_key(
                            fixture_id=fixture_id,
                            elapsed=elapsed,
                            extra=extra,
                            type_=type_,
                            detail=detail,
                            player_id=player_id,
                            assist_id=assist_id,
                            role="assist",
                        ),
                        fixture_id=fixture_id,
                        kind=ScoringEventKind.ASSIST,
                        status=EventStatus.CONFIRMED,
                        player_id=assist_id,
                        team_id=team_id,
                        related_player_id=player_id,
                        minute_elapsed=elapsed,
                        minute_extra=extra,
                        sources=("events",),
                        raw_type=type_,
                        raw_detail=detail,
                    )
                )

        elif detail == "Penalty":
            event_goal_count += 1
            event_penalty_scored += 1
            status, codes = _require_player(player_id)
            out.append(
                NormalizedScoringEvent(
                    provider_event_key=event_provider_key(
                        fixture_id=fixture_id,
                        elapsed=elapsed,
                        extra=extra,
                        type_=type_,
                        detail=detail,
                        player_id=player_id,
                        assist_id=None,
                        role="penalty_scored",
                    ),
                    fixture_id=fixture_id,
                    kind=ScoringEventKind.PENALTY_SCORED,
                    status=status,
                    player_id=player_id,
                    team_id=team_id,
                    minute_elapsed=elapsed,
                    minute_extra=extra,
                    sources=("events",),
                    anomaly_codes=codes,
                    raw_type=type_,
                    raw_detail=detail,
                )
            )

        elif detail == "Own Goal":
            status, codes = _require_player(player_id)
            notes = ("team_id is provider event team (often the benefiting side for own goals)",)
            out.append(
                NormalizedScoringEvent(
                    provider_event_key=event_provider_key(
                        fixture_id=fixture_id,
                        elapsed=elapsed,
                        extra=extra,
                        type_=type_,
                        detail=detail,
                        player_id=player_id,
                        assist_id=None,
                        role="own_goal",
                    ),
                    fixture_id=fixture_id,
                    kind=ScoringEventKind.OWN_GOAL,
                    status=status,
                    player_id=player_id,
                    team_id=team_id,
                    minute_elapsed=elapsed,
                    minute_extra=extra,
                    sources=("events",),
                    anomaly_codes=codes,
                    raw_type=type_,
                    raw_detail=detail,
                    notes=notes,
                )
            )

        elif detail == "Missed Penalty":
            miss_from_events.append(
                _MissCandidate(
                    player_id=player_id,
                    team_id=team_id,
                    minute_elapsed=elapsed,
                    minute_extra=extra,
                    sources=("events",),
                    raw_type=type_,
                    raw_detail=detail,
                    key_seed=event_provider_key(
                        fixture_id=fixture_id,
                        elapsed=elapsed,
                        extra=extra,
                        type_=type_,
                        detail=detail,
                        player_id=player_id,
                        assist_id=None,
                        role="penalty_miss",
                    ),
                    from_events=True,
                )
            )

        else:
            out.append(
                NormalizedScoringEvent(
                    provider_event_key=event_provider_key(
                        fixture_id=fixture_id,
                        elapsed=elapsed,
                        extra=extra,
                        type_=type_,
                        detail=detail,
                        player_id=player_id,
                        assist_id=assist_id,
                        role="unknown",
                    ),
                    fixture_id=fixture_id,
                    kind=ScoringEventKind.UNKNOWN,
                    status=EventStatus.INSUFFICIENT,
                    player_id=player_id,
                    team_id=team_id,
                    minute_elapsed=elapsed,
                    minute_extra=extra,
                    sources=("events",),
                    anomaly_codes=(AnomalyCode.UNKNOWN_GOAL_DETAIL,),
                    raw_type=type_,
                    raw_detail=detail,
                    notes=("unrecognized Goal detail; not scored silently",),
                )
            )
            fixture_anomalies.append(AnomalyCode.UNKNOWN_GOAL_DETAIL)

    stats = _aggregate_player_stats(player_rows)

    if stats.goals_total != event_goal_count:
        fixture_anomalies.append(AnomalyCode.GOAL_COUNT_MISMATCH)
        fixture_notes.append(
            f"goals watchdog: events={event_goal_count} players.goals.total={stats.goals_total}"
        )
    if stats.assists_total != event_assist_count:
        fixture_anomalies.append(AnomalyCode.ASSIST_COUNT_MISMATCH)
        fixture_notes.append(
            f"assists watchdog: events={event_assist_count} "
            f"players.goals.assists={stats.assists_total}"
        )
    if stats.penalty_scored != event_penalty_scored:
        fixture_anomalies.append(AnomalyCode.PENALTY_SCORED_MISMATCH)
        fixture_notes.append(
            f"penalty.scored watchdog: events={event_penalty_scored} players={stats.penalty_scored}"
        )

    # Never invent goals/assists from stats when events are the primary source.
    if stats.goals_total > event_goal_count:
        fixture_anomalies.append(AnomalyCode.STATS_ONLY_GOAL)
    if stats.assists_total > event_assist_count:
        fixture_anomalies.append(AnomalyCode.STATS_ONLY_ASSIST)

    miss_candidates = list(miss_from_events)
    event_miss_player_counts = Counter(
        m.player_id for m in miss_from_events if m.player_id is not None
    )
    for pid, count in stats.missed_by_player.items():
        already = event_miss_player_counts.get(pid, 0)
        for ordinal in range(already, count):
            miss_candidates.append(
                _MissCandidate(
                    player_id=pid,
                    team_id=stats.team_by_player.get(pid),
                    minute_elapsed=None,
                    minute_extra=None,
                    sources=("players",),
                    raw_type=None,
                    raw_detail=None,
                    key_seed=stats_provider_key(
                        fixture_id=fixture_id,
                        kind="penalty_missed",
                        player_id=pid,
                        ordinal=ordinal,
                    ),
                    from_events=False,
                )
            )
            fixture_anomalies.append(AnomalyCode.EVENTS_MISSING_MISSED_PENALTY)

    save_candidates: list[_SaveCandidate] = []
    for pid, count in stats.saved_by_player.items():
        for ordinal in range(count):
            save_candidates.append(
                _SaveCandidate(
                    player_id=pid,
                    team_id=stats.team_by_player.get(pid),
                    ordinal=ordinal,
                )
            )

    out.extend(
        _reconcile_penalty_outcomes(
            fixture_id=fixture_id,
            misses=miss_candidates,
            saves=save_candidates,
            fixture_anomalies=fixture_anomalies,
        )
    )

    ordered = tuple(sorted(out, key=_event_sort_key))
    # Deduplicate anomaly codes while preserving order
    seen: set[AnomalyCode] = set()
    uniq_anomalies: list[AnomalyCode] = []
    for code in fixture_anomalies:
        if code not in seen:
            seen.add(code)
            uniq_anomalies.append(code)

    return NormalizationResult(
        fixture_id=fixture_id,
        events=ordered,
        anomalies=tuple(uniq_anomalies),
        notes=tuple(fixture_notes),
    )


def _reconcile_penalty_outcomes(
    *,
    fixture_id: int,
    misses: Sequence[_MissCandidate],
    saves: Sequence[_SaveCandidate],
    fixture_anomalies: list[AnomalyCode],
) -> list[NormalizedScoringEvent]:
    """Pair missed penalties with GK saves; surface orphans as anomalies.

    Classification:
    - miss + save → PENALTY_MISSED (taker) + PENALTY_SAVED (GK)
    - miss without save → PENALTY_OFF_TARGET (taker)
    - save without miss → PENALTY_SAVED with INSUFFICIENT / orphan anomaly
    """
    result: list[NormalizedScoringEvent] = []
    unpaired_saves = list(saves)

    for miss in misses:
        paired_save: _SaveCandidate | None = None
        if unpaired_saves:
            # Prefer GK of the opposing team when team ids are known.
            if miss.team_id is not None:
                for idx, save in enumerate(unpaired_saves):
                    if save.team_id is not None and save.team_id != miss.team_id:
                        paired_save = unpaired_saves.pop(idx)
                        break
            if paired_save is None:
                paired_save = unpaired_saves.pop(0)

        if paired_save is not None:
            sources = tuple(dict.fromkeys([*miss.sources, *paired_save.sources]))
            status = EventStatus.CONFIRMED if miss.from_events else EventStatus.PROVISIONAL
            codes: tuple[AnomalyCode, ...] = ()
            if not miss.from_events:
                codes = (AnomalyCode.EVENTS_MISSING_MISSED_PENALTY,)
            miss_status, miss_codes = _require_player(miss.player_id)
            if miss_status != EventStatus.CONFIRMED:
                status = miss_status
            codes = tuple(dict.fromkeys([*codes, *miss_codes]))

            result.append(
                NormalizedScoringEvent(
                    provider_event_key=f"{miss.key_seed}|outcome=saved",
                    fixture_id=fixture_id,
                    kind=ScoringEventKind.PENALTY_MISSED,
                    status=status,
                    player_id=miss.player_id,
                    team_id=miss.team_id,
                    related_player_id=paired_save.player_id,
                    related_team_id=paired_save.team_id,
                    minute_elapsed=miss.minute_elapsed,
                    minute_extra=miss.minute_extra,
                    sources=sources,
                    anomaly_codes=codes,
                    raw_type=miss.raw_type,
                    raw_detail=miss.raw_detail,
                    notes=("classified as saved via players.penalty.saved",),
                )
            )
            save_status, save_codes = _require_player(paired_save.player_id)
            if status == EventStatus.PROVISIONAL and save_status == EventStatus.CONFIRMED:
                save_status = EventStatus.PROVISIONAL
            result.append(
                NormalizedScoringEvent(
                    provider_event_key=stats_provider_key(
                        fixture_id=fixture_id,
                        kind="penalty_saved",
                        player_id=paired_save.player_id,
                        ordinal=paired_save.ordinal,
                    ),
                    fixture_id=fixture_id,
                    kind=ScoringEventKind.PENALTY_SAVED,
                    status=save_status if not codes else status,
                    player_id=paired_save.player_id,
                    team_id=paired_save.team_id,
                    related_player_id=miss.player_id,
                    related_team_id=miss.team_id,
                    minute_elapsed=miss.minute_elapsed,
                    minute_extra=miss.minute_extra,
                    sources=sources,
                    anomaly_codes=codes + save_codes,
                    raw_type=None,
                    raw_detail=None,
                    notes=("primary source: players.penalty.saved",),
                )
            )
        else:
            status, codes = _require_player(miss.player_id)
            notes = ["no unpaired players.penalty.saved; classified off-target"]
            if not miss.from_events:
                # Stats-only miss without save may be incomplete provider data.
                status = EventStatus.PROVISIONAL
                codes = tuple(
                    dict.fromkeys(
                        [
                            *codes,
                            AnomalyCode.EVENTS_MISSING_MISSED_PENALTY,
                            AnomalyCode.ORPHAN_PENALTY_MISS,
                        ]
                    )
                )
                fixture_anomalies.append(AnomalyCode.ORPHAN_PENALTY_MISS)
                notes.append(
                    "stats-only miss without save not treated as silent off-target certainty"
                )
            result.append(
                NormalizedScoringEvent(
                    provider_event_key=f"{miss.key_seed}|outcome=off_target",
                    fixture_id=fixture_id,
                    kind=ScoringEventKind.PENALTY_OFF_TARGET,
                    status=status,
                    player_id=miss.player_id,
                    team_id=miss.team_id,
                    minute_elapsed=miss.minute_elapsed,
                    minute_extra=miss.minute_extra,
                    sources=miss.sources,
                    anomaly_codes=codes,
                    raw_type=miss.raw_type,
                    raw_detail=miss.raw_detail,
                    notes=tuple(notes),
                )
            )

    for save in unpaired_saves:
        status, codes = _require_player(save.player_id)
        codes = tuple(dict.fromkeys([*codes, AnomalyCode.ORPHAN_PENALTY_SAVE]))
        result.append(
            NormalizedScoringEvent(
                provider_event_key=stats_provider_key(
                    fixture_id=fixture_id,
                    kind="penalty_saved",
                    player_id=save.player_id,
                    ordinal=save.ordinal,
                ),
                fixture_id=fixture_id,
                kind=ScoringEventKind.PENALTY_SAVED,
                status=EventStatus.INSUFFICIENT,
                player_id=save.player_id,
                team_id=save.team_id,
                sources=save.sources,
                anomaly_codes=codes,
                notes=("penalty.saved without matching miss/taker; not resolved silently",),
            )
        )
        fixture_anomalies.append(AnomalyCode.ORPHAN_PENALTY_SAVE)

    return result


@dataclass
class _StatsAgg:
    goals_total: int = 0
    assists_total: int = 0
    penalty_scored: int = 0
    missed_by_player: dict[int, int] = field(default_factory=dict)
    saved_by_player: dict[int, int] = field(default_factory=dict)
    team_by_player: dict[int, int] = field(default_factory=dict)


def _aggregate_player_stats(rows: Iterable[tuple[int | None, dict[str, Any]]]) -> _StatsAgg:
    agg = _StatsAgg()
    for team_id, player_block in rows:
        player = player_block.get("player") or {}
        pid = player.get("id")
        stats_list = player_block.get("statistics") or []
        if not stats_list:
            continue
        st = stats_list[0] or {}
        goals = st.get("goals") or {}
        pen = st.get("penalty") or {}
        agg.goals_total += int(goals.get("total") or 0)
        agg.assists_total += int(goals.get("assists") or 0)
        agg.penalty_scored += int(pen.get("scored") or 0)
        if pid is not None:
            if team_id is not None:
                agg.team_by_player[pid] = team_id
            missed = int(pen.get("missed") or 0)
            saved = int(pen.get("saved") or 0)
            if missed:
                agg.missed_by_player[pid] = agg.missed_by_player.get(pid, 0) + missed
            if saved:
                agg.saved_by_player[pid] = agg.saved_by_player.get(pid, 0) + saved
    return agg


def _iter_player_rows(
    players_payload: Mapping[str, Any] | None,
) -> Iterable[tuple[int | None, dict[str, Any]]]:
    if not players_payload:
        return
    for team_block in players_payload.get("response") or []:
        team = team_block.get("team") or {}
        team_id = team.get("id")
        for player_block in team_block.get("players") or []:
            yield team_id, player_block


def _response_list(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    response = payload.get("response") or []
    return [e for e in response if isinstance(e, dict)]


def _require_player(player_id: Any) -> tuple[EventStatus, tuple[AnomalyCode, ...]]:
    if player_id is None:
        return EventStatus.INSUFFICIENT, (AnomalyCode.MISSING_PLAYER_ID,)
    return EventStatus.CONFIRMED, ()


def _event_sort_key(event: NormalizedScoringEvent) -> tuple[Any, ...]:
    return (
        event.minute_elapsed is None,
        event.minute_elapsed if event.minute_elapsed is not None else 10**9,
        event.minute_extra is None,
        event.minute_extra if event.minute_extra is not None else -1,
        event.kind.value,
        event.player_id if event.player_id is not None else -1,
        event.provider_event_key,
    )
