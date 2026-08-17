"""Mappa stats persistite (EP04-05) verso l'input della formula (EP07-01)."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from fantasy_ratings.eligibility import (
    SUBSTITUTION_EVENT_TYPE,
    is_second_half_stoppage,
)
from fantasy_ratings.input import PlayerMatchInput, relevant_events_from_statistics
from sports_data.fixtures.models import MatchEvent, PlayerMatchStat
from sports_data.normalization.types import ScoringEventKind


def own_goal_provider_ids(events: Iterable[MatchEvent]) -> set[int]:
    ids: set[int] = set()
    for event in events:
        if not event.is_active:
            continue
        if event.scoring_kind != ScoringEventKind.OWN_GOAL.value:
            continue
        if event.athlete_provider_id is not None:
            ids.add(int(event.athlete_provider_id))
    return ids


def stoppage_entry_provider_ids(events: Iterable[MatchEvent]) -> set[int]:
    ids: set[int] = set()
    for event in events:
        if not event.is_active:
            continue
        if str(event.event_type or "").lower() != SUBSTITUTION_EVENT_TYPE:
            continue
        if not is_second_half_stoppage(event.minute_elapsed, event.minute_extra):
            continue
        if event.related_athlete_provider_id is not None:
            ids.add(int(event.related_athlete_provider_id))
    return ids


def player_input_from_stat(
    *,
    fixture_provider_id: int,
    stat: PlayerMatchStat,
    own_goal_ids: set[int],
    stoppage_entry_ids: set[int] | None = None,
) -> PlayerMatchInput:
    statistics = dict(stat.stats_json or {})
    provider_rating = _parse_rating(stat.provider_rating)
    stoppage_ids = stoppage_entry_ids or set()
    return PlayerMatchInput(
        fixture_id=fixture_provider_id,
        player_id=stat.athlete_provider_id,
        player_name="",
        team_id=None,
        position=stat.position_raw,
        minutes=stat.minutes,
        substitute=bool(stat.is_substitute),
        provider_rating=provider_rating,
        statistics=statistics,
        relevant_events=relevant_events_from_statistics(
            statistics,
            own_goal=stat.athlete_provider_id in own_goal_ids,
        ),
        stats_hash=stat.stats_hash,
        entered_in_stoppage=stat.athlete_provider_id in stoppage_ids,
    )


def inputs_from_fixture_stats(
    *,
    fixture_provider_id: int,
    stats: Iterable[PlayerMatchStat],
    events: Iterable[MatchEvent],
) -> list[PlayerMatchInput]:
    own_goals = own_goal_provider_ids(events)
    stoppage_ids = stoppage_entry_provider_ids(events)
    return [
        player_input_from_stat(
            fixture_provider_id=fixture_provider_id,
            stat=stat,
            own_goal_ids=own_goals,
            stoppage_entry_ids=stoppage_ids,
        )
        for stat in stats
    ]


def _parse_rating(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))
