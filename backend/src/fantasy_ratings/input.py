"""Input calciatore-partita e flag di evento rilevante (EP07-01 / EP07-02)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fantasy_ratings.eligibility import stoppage_entry_player_ids_from_payload


@dataclass(frozen=True)
class RelevantEvents:
    goal: bool = False
    assist: bool = False
    penalty_missed: bool = False
    own_goal: bool = False
    red_card: bool = False

    def any_relevant(self, flags: tuple[str, ...]) -> bool:
        mapping = {
            "goal": self.goal,
            "assist": self.assist,
            "penalty_missed": self.penalty_missed,
            "own_goal": self.own_goal,
            "red_card": self.red_card,
        }
        return any(mapping.get(name, False) for name in flags)

    def as_dict(self) -> dict[str, bool]:
        return {
            "goal": self.goal,
            "assist": self.assist,
            "penalty_missed": self.penalty_missed,
            "own_goal": self.own_goal,
            "red_card": self.red_card,
        }


@dataclass(frozen=True)
class PlayerMatchInput:
    fixture_id: int
    player_id: int
    player_name: str
    team_id: int | None
    position: str | None
    minutes: int | None
    substitute: bool
    provider_rating: float | None
    statistics: dict[str, Any]
    relevant_events: RelevantEvents = field(default_factory=RelevantEvents)
    stats_hash: str | None = None
    entered_in_stoppage: bool = False

    @property
    def goals_total(self) -> int:
        return _as_int(_dig(self.statistics, "goals.total"))

    @property
    def assists_total(self) -> int:
        return _as_int(_dig(self.statistics, "goals.assists"))

    def as_input_snapshot(self) -> dict[str, Any]:
        """Snapshot ricostruibile: niente nome calciatore nei log persistiti."""
        return {
            "fixture_provider_id": self.fixture_id,
            "athlete_provider_id": self.player_id,
            "team_provider_id": self.team_id,
            "position": self.position,
            "minutes": self.minutes,
            "substitute": self.substitute,
            "statistics": self.statistics,
            "relevant_events": self.relevant_events.as_dict(),
            "entered_in_stoppage": self.entered_in_stoppage,
            "stats_hash": self.stats_hash,
        }


def iter_players_from_payload(
    *,
    fixture_id: int,
    players_payload: dict[str, Any],
    own_goal_player_ids: set[int] | None = None,
    stoppage_entry_player_ids: set[int] | None = None,
) -> list[PlayerMatchInput]:
    """Flatten API-Football ``/fixtures/players`` response into inputs."""
    own_goals = own_goal_player_ids or set()
    stoppage_entries = stoppage_entry_player_ids or set()
    out: list[PlayerMatchInput] = []
    for team_block in players_payload.get("response") or []:
        team = team_block.get("team") or {}
        team_id = team.get("id")
        for entry in team_block.get("players") or []:
            player = entry.get("player") or {}
            stats_list = entry.get("statistics") or []
            stats = stats_list[0] if stats_list else {}
            games = stats.get("games") or {}
            cards = stats.get("cards") or {}
            goals = stats.get("goals") or {}
            penalty = stats.get("penalty") or {}

            minutes = games.get("minutes")
            provider_rating = _parse_rating(games.get("rating"))
            relevant = RelevantEvents(
                goal=_as_int(goals.get("total")) > 0,
                assist=_as_int(goals.get("assists")) > 0,
                penalty_missed=_as_int(penalty.get("missed")) > 0,
                own_goal=player.get("id") in own_goals,
                red_card=_as_int(cards.get("red")) > 0,
            )
            out.append(
                PlayerMatchInput(
                    fixture_id=fixture_id,
                    player_id=int(player["id"]),
                    player_name=str(player.get("name") or ""),
                    team_id=int(team_id) if team_id is not None else None,
                    position=games.get("position"),
                    minutes=int(minutes) if minutes is not None else None,
                    substitute=bool(games.get("substitute")),
                    provider_rating=provider_rating,
                    statistics=stats,
                    relevant_events=relevant,
                    entered_in_stoppage=int(player["id"]) in stoppage_entries,
                )
            )
    return out


def own_goal_player_ids_from_events(events_payload: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for event in events_payload.get("response") or []:
        if event.get("type") == "Goal" and event.get("detail") == "Own Goal":
            player = event.get("player") or {}
            pid = player.get("id")
            if pid is not None:
                ids.add(int(pid))
    return ids


def stoppage_entry_ids_from_events(events_payload: dict[str, Any]) -> set[int]:
    return stoppage_entry_player_ids_from_payload(events_payload)


def relevant_events_from_statistics(
    statistics: dict[str, Any],
    *,
    own_goal: bool = False,
) -> RelevantEvents:
    goals = statistics.get("goals") if isinstance(statistics.get("goals"), dict) else {}
    penalty = statistics.get("penalty") if isinstance(statistics.get("penalty"), dict) else {}
    cards = statistics.get("cards") if isinstance(statistics.get("cards"), dict) else {}
    return RelevantEvents(
        goal=_as_int(goals.get("total")) > 0,
        assist=_as_int(goals.get("assists")) > 0,
        penalty_missed=_as_int(penalty.get("missed")) > 0,
        own_goal=own_goal,
        red_card=_as_int(cards.get("red")) > 0,
    )


def _dig(stats: dict[str, Any], path: str) -> Any:
    cur: Any = stats
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_rating(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
