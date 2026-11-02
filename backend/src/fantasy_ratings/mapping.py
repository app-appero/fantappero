"""Mappa stats persistite (EP04-05) verso l'input della formula (EP07-01)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from uuid import UUID

from fantasy_ratings.bonus import BonusMalusInput
from fantasy_ratings.eligibility import (
    SUBSTITUTION_EVENT_TYPE,
    is_second_half_stoppage,
)
from fantasy_ratings.input import PlayerMatchInput, relevant_events_from_statistics
from sports_data.fixtures.models import Fixture, MatchEvent, PlayerMatchStat
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


def own_goal_counts_by_provider_id(events: Iterable[MatchEvent]) -> dict[int, int]:
    """Conteggio autogol per calciatore da ``match_event`` attivi (FR-SCO-02).

    Ogni riga ``match_event`` ha ``provider_event_key`` univoco: sommare i
    conteggi qui non puo' contare due volte lo stesso autogol.
    """
    counts: dict[int, int] = {}
    for event in events:
        if not event.is_active:
            continue
        if event.scoring_kind != ScoringEventKind.OWN_GOAL.value:
            continue
        if event.athlete_provider_id is None:
            continue
        pid = int(event.athlete_provider_id)
        counts[pid] = counts.get(pid, 0) + 1
    return counts


def penalty_counts_by_provider_id(
    events: Iterable[MatchEvent],
) -> tuple[dict[int, int], dict[int, int]]:
    """Rigori sbagliati e parati per calciatore da ``match_event`` attivi (FR-SCO-02).

    Il malus del rigore sbagliato non deve dipendere solo da
    ``stats_json.penalty``: la statistica del provider puo' mancare o arrivare
    dopo l'evento. Un rigore sbagliato e' sia ``penalty_missed`` (parato dal
    portiere) sia ``penalty_off_target`` (fuori/palo): in entrambi i casi il
    rigorista ha sbagliato. Ritorna ``(sbagliati, parati)``.
    """
    missed: dict[int, int] = {}
    saved: dict[int, int] = {}
    for event in events:
        if not event.is_active or event.athlete_provider_id is None:
            continue
        pid = int(event.athlete_provider_id)
        if event.scoring_kind in (
            ScoringEventKind.PENALTY_MISSED.value,
            ScoringEventKind.PENALTY_OFF_TARGET.value,
        ):
            missed[pid] = missed.get(pid, 0) + 1
        elif event.scoring_kind == ScoringEventKind.PENALTY_SAVED.value:
            saved[pid] = saved.get(pid, 0) + 1
    return missed, saved


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


def team_goals_conceded(fixture: Fixture, club_id: UUID | None) -> int | None:
    """Gol subiti dalla squadra di ``club_id`` nella partita, se il risultato e' noto."""
    if club_id is None:
        return None
    if club_id == fixture.home_club_id:
        return fixture.away_goals
    if club_id == fixture.away_club_id:
        return fixture.home_goals
    return None


def bonus_input_from_stat(
    *,
    fixture: Fixture,
    stat: PlayerMatchStat,
    role: str | None,
    own_goal_counts: dict[int, int],
    penalty_missed_counts: dict[int, int] | None = None,
    penalty_saved_counts: dict[int, int] | None = None,
) -> BonusMalusInput:
    statistics = dict(stat.stats_json or {})
    goals = statistics.get("goals") if isinstance(statistics.get("goals"), dict) else {}
    cards = statistics.get("cards") if isinstance(statistics.get("cards"), dict) else {}
    penalty = statistics.get("penalty") if isinstance(statistics.get("penalty"), dict) else {}
    return BonusMalusInput(
        goals=_as_int(goals.get("total")),
        assists=_as_int(goals.get("assists")),
        yellow_card=_as_int(cards.get("yellow")) > 0,
        red_card=_as_int(cards.get("red")) > 0,
        own_goals=own_goal_counts.get(stat.athlete_provider_id, 0),
        # Il valore piu' alto tra statistica ed eventi (mai la somma: sono la
        # stessa cosa vista da due feed, sommarli conterebbe il rigore due volte).
        penalty_missed=max(
            _as_int(penalty.get("missed")),
            (penalty_missed_counts or {}).get(stat.athlete_provider_id, 0),
        ),
        penalty_saved=max(
            _as_int(penalty.get("saved")),
            (penalty_saved_counts or {}).get(stat.athlete_provider_id, 0),
        ),
        role=role,  # type: ignore[arg-type]
        team_goals_conceded=team_goals_conceded(fixture, stat.club_id),
    )


def bonus_inputs_from_fixture_stats(
    *,
    fixture: Fixture,
    stats: Iterable[PlayerMatchStat],
    events: Iterable[MatchEvent],
    roles_by_provider_id: dict[int, str | None],
) -> list[BonusMalusInput]:
    events = list(events)
    own_goal_counts = own_goal_counts_by_provider_id(events)
    penalty_missed_counts, penalty_saved_counts = penalty_counts_by_provider_id(events)
    return [
        bonus_input_from_stat(
            fixture=fixture,
            stat=stat,
            role=roles_by_provider_id.get(stat.athlete_provider_id),
            own_goal_counts=own_goal_counts,
            penalty_missed_counts=penalty_missed_counts,
            penalty_saved_counts=penalty_saved_counts,
        )
        for stat in stats
    ]


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
