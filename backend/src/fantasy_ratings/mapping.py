"""Mappa stats persistite (EP04-05) verso l'input della formula (EP07-01)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from fantasy_ratings.bonus import BonusMalusInput
from fantasy_ratings.eligibility import (
    SUBSTITUTION_EVENT_TYPE,
    is_second_half_stoppage,
)
from fantasy_ratings.input import PlayerMatchInput, relevant_events_from_statistics
from sports_data.fixtures.models import Fixture, MatchEvent, PlayerMatchStat
from sports_data.normalization.types import EventStatus, ScoringEventKind


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


@dataclass(frozen=True)
class EventBonusCounts:
    """Conteggi bonus/malus per calciatore ricavati da ``match_event`` (FR-SCO-02).

    Servono come rete di sicurezza: le statistiche del provider
    (``stats_json``) possono mancare o arrivare dopo gli eventi della partita.
    Per ogni voce si usa il valore piu' alto tra statistica ed eventi, mai la
    somma: sono lo stesso fatto visto da due feed e sommarli lo conterebbe due
    volte.
    """

    goals: dict[int, int] = field(default_factory=dict)
    assists: dict[int, int] = field(default_factory=dict)
    yellow_cards: dict[int, int] = field(default_factory=dict)
    red_cards: dict[int, int] = field(default_factory=dict)
    penalty_missed: dict[int, int] = field(default_factory=dict)
    penalty_saved: dict[int, int] = field(default_factory=dict)


# Stati che non vanno mai a punteggio: dati in contraddizione o insufficienti.
_EXCLUDED_EVENT_STATUSES = frozenset({EventStatus.ANOMALY.value, EventStatus.INSUFFICIENT.value})


_TIMELINE_STATUS = "timeline"


def event_bonus_counts(events: Iterable[MatchEvent]) -> EventBonusCounts:
    """Conta gol, assist, cartellini e rigori per calciatore da eventi attivi.

    ``match_event`` contiene due viste dello stesso fatto: le righe grezze della
    cronologia (``status == "timeline"``, quelle mostrate in "Cronologia") e le
    righe normalizzate per il punteggio (con ``scoring_kind``). Si contano
    separatamente e per ogni calciatore si prende il valore piu' alto (mai la
    somma), cosi' un fatto presente in cronologia dà il bonus/malus anche se la
    riga normalizzata non e' stata prodotta.
    """
    scoring = EventBonusCounts()
    timeline = EventBonusCounts()

    def bump(target: dict[int, int], pid: int | None) -> None:
        if pid is not None:
            target[int(pid)] = target.get(int(pid), 0) + 1

    for event in events:
        if not event.is_active:
            continue
        status = getattr(event, "status", None)
        if status in _EXCLUDED_EVENT_STATUSES:
            continue
        pid = event.athlete_provider_id
        kind = event.scoring_kind
        etype = str(event.event_type or "").lower()
        detail = str(event.event_detail or "").lower()

        if status == _TIMELINE_STATUS:
            if etype == "goal":
                if detail in ("normal goal", "penalty"):
                    bump(timeline.goals, pid)
                    bump(timeline.assists, getattr(event, "related_athlete_provider_id", None))
                elif "missed" in detail:
                    bump(timeline.penalty_missed, pid)
            elif etype == "card":
                if "red" in detail or "second yellow" in detail:
                    bump(timeline.red_cards, pid)
                elif "yellow" in detail:
                    bump(timeline.yellow_cards, pid)
            continue

        if pid is None:
            continue
        if kind in (ScoringEventKind.GOAL.value, ScoringEventKind.PENALTY_SCORED.value):
            bump(scoring.goals, pid)
        elif kind == ScoringEventKind.ASSIST.value:
            bump(scoring.assists, pid)
        elif kind in (
            ScoringEventKind.PENALTY_MISSED.value,
            ScoringEventKind.PENALTY_OFF_TARGET.value,
        ):
            # Parato o fuori/palo: in entrambi i casi il rigorista ha sbagliato.
            bump(scoring.penalty_missed, pid)
        elif kind == ScoringEventKind.PENALTY_SAVED.value:
            bump(scoring.penalty_saved, pid)
        elif etype == "card":
            if "red" in detail or "second yellow" in detail:
                bump(scoring.red_cards, pid)
            elif "yellow" in detail:
                bump(scoring.yellow_cards, pid)

    def merge(left: dict[int, int], right: dict[int, int]) -> dict[int, int]:
        return {pid: max(left.get(pid, 0), right.get(pid, 0)) for pid in {*left, *right}}

    return EventBonusCounts(
        goals=merge(scoring.goals, timeline.goals),
        assists=merge(scoring.assists, timeline.assists),
        yellow_cards=merge(scoring.yellow_cards, timeline.yellow_cards),
        red_cards=merge(scoring.red_cards, timeline.red_cards),
        penalty_missed=merge(scoring.penalty_missed, timeline.penalty_missed),
        penalty_saved=merge(scoring.penalty_saved, timeline.penalty_saved),
    )


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
    event_counts: EventBonusCounts | None = None,
) -> BonusMalusInput:
    statistics = dict(stat.stats_json or {})
    goals = statistics.get("goals") if isinstance(statistics.get("goals"), dict) else {}
    cards = statistics.get("cards") if isinstance(statistics.get("cards"), dict) else {}
    penalty = statistics.get("penalty") if isinstance(statistics.get("penalty"), dict) else {}
    counts = event_counts or EventBonusCounts()
    pid = stat.athlete_provider_id
    # Valore piu' alto tra statistica ed eventi (vedi ``EventBonusCounts``).
    return BonusMalusInput(
        goals=max(_as_int(goals.get("total")), counts.goals.get(pid, 0)),
        assists=max(_as_int(goals.get("assists")), counts.assists.get(pid, 0)),
        yellow_card=_as_int(cards.get("yellow")) > 0 or counts.yellow_cards.get(pid, 0) > 0,
        red_card=_as_int(cards.get("red")) > 0 or counts.red_cards.get(pid, 0) > 0,
        own_goals=own_goal_counts.get(pid, 0),
        penalty_missed=max(_as_int(penalty.get("missed")), counts.penalty_missed.get(pid, 0)),
        penalty_saved=max(_as_int(penalty.get("saved")), counts.penalty_saved.get(pid, 0)),
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
    event_counts = event_bonus_counts(events)
    return [
        bonus_input_from_stat(
            fixture=fixture,
            stat=stat,
            role=roles_by_provider_id.get(stat.athlete_provider_id),
            own_goal_counts=own_goal_counts,
            event_counts=event_counts,
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
