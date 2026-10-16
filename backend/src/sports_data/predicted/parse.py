"""Lettura difensiva delle risposte FotMob.

Lo schema osservato è ``{"lineup": {"lineupType", "source", "homeTeam", "awayTeam"}}``.
Il parser accetta anche qualche alias, e scarta ciò che non è un oggetto atteso
invece di assumere che il JSON sia una formazione utilizzabile.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

_FORMATION = re.compile(r"^\d(?:-\d){1,4}$")
_UNCERTAIN = ("doubtful", "back in training", "a few weeks", "unknown")
_CONFIRMED = {"confirmed", "official"}
_PREDICTED = {"predicted", "expected", "probable"}


@dataclass(frozen=True)
class ParsedPlayer:
    fotmob_id: int | None
    name: str
    shirt_number: int | None
    is_starter: bool
    is_unavailable: bool
    unavailability_type: str | None
    unavailability_label: str | None
    expected_return_at: datetime | None
    uncertain: bool
    layout_x: float | None
    layout_y: float | None


@dataclass(frozen=True)
class ParsedSide:
    name: str
    formation: str | None
    coach_name: str | None
    players: tuple[ParsedPlayer, ...]


@dataclass(frozen=True)
class ParsedLineup:
    lineup_type: str
    source: str | None
    home: ParsedSide | None
    away: ParsedSide | None
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ParsedMatchRef:
    fotmob_match_id: int
    home_name: str
    away_name: str


def parse_lineup_payload(payload: object) -> ParsedLineup:
    """Estrae la formazione. Payload illeggibile → formazione vuota, non un'eccezione."""
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return ParsedLineup("unknown", None, None, None, ("invalid_schema",))
    lineup = payload.get("lineup", payload)
    if not isinstance(lineup, dict):
        return ParsedLineup("unknown", None, None, None, ("invalid_schema",))
    source = _text(lineup.get("source"))
    return ParsedLineup(
        lineup_type=normalize_lineup_type(
            _text(lineup.get("lineupType") or lineup.get("lineup_type"))
        ),
        source=source,
        home=_parse_side(lineup.get("homeTeam") or lineup.get("home"), warnings, "home"),
        away=_parse_side(lineup.get("awayTeam") or lineup.get("away"), warnings, "away"),
        warnings=tuple(warnings),
    )


def parse_matches_by_date(payload: object) -> tuple[ParsedMatchRef, ...]:
    """Elenco partite di un giorno. Accetta le forme più comuni del wrapper."""
    found: list[ParsedMatchRef] = []
    for item in _match_nodes(payload):
        match_id = _int(item.get("id") if "id" in item else item.get("matchId"))
        home = _team_name(item, "home")
        away = _team_name(item, "away")
        if match_id is None or not home or not away:
            continue
        found.append(ParsedMatchRef(fotmob_match_id=match_id, home_name=home, away_name=away))
    return tuple(found)


def normalize_lineup_type(value: str | None) -> str:
    """``confirmed`` solo se il provider usa un valore esplicito di formazione ufficiale."""
    normalized = (value or "").strip().lower()
    if normalized in _CONFIRMED:
        return "confirmed"
    if normalized in _PREDICTED:
        return "predicted"
    return "unknown"


def formation_is_valid(value: str | None) -> bool:
    if not value:
        return False
    return _FORMATION.match(value.strip()) is not None


def is_uncertain_absence(label: str | None, kind: str | None) -> bool:
    blob = f"{label or ''} {kind or ''}".lower()
    return any(phrase in blob for phrase in _UNCERTAIN)


def _parse_side(raw: object, warnings: list[str], side: str) -> ParsedSide | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        warnings.append(f"{side}_invalid")
        return None
    name = _text(raw.get("name")) or ""
    formation = _text(raw.get("formation"))
    if formation and not formation_is_valid(formation):
        warnings.append(f"{side}_formation")
        formation = formation.strip()[:32]
    elif not formation:
        warnings.append(f"{side}_formation_missing")
    players: list[ParsedPlayer] = []
    starters = raw.get("starters")
    if starters is not None and not isinstance(starters, list):
        warnings.append(f"{side}_starters_invalid")
        starters = []
    for item in starters or []:
        player = _parse_player(item, is_starter=True, is_unavailable=False)
        if player is not None:
            players.append(player)
    bench_raw = raw.get("substitutes")
    if bench_raw is None:
        bench_raw = raw.get("bench")
    if bench_raw is None:
        bench_raw = raw.get("subs")
    if isinstance(bench_raw, list):
        for item in bench_raw:
            player = _parse_player(item, is_starter=False, is_unavailable=False)
            if player is not None:
                players.append(player)
    unavailable = raw.get("unavailable")
    if isinstance(unavailable, list):
        for item in unavailable:
            player = _parse_player(item, is_starter=False, is_unavailable=True)
            if player is not None:
                players.append(player)
    return ParsedSide(
        name=name,
        formation=formation.strip() if formation else None,
        coach_name=_coach_name(raw.get("coach")),
        players=tuple(players),
    )


def _parse_player(raw: object, *, is_starter: bool, is_unavailable: bool) -> ParsedPlayer | None:
    if not isinstance(raw, dict):
        return None
    name = _text(raw.get("name"))
    if not name:
        return None
    absence = raw.get("unavailability") if isinstance(raw.get("unavailability"), dict) else {}
    kind = _text(absence.get("type")) if isinstance(absence, dict) else None
    label = None
    expected = None
    if isinstance(absence, dict):
        label = _text(absence.get("expectedReturn")) or _text(absence.get("expected_return"))
        expected = _datetime(
            absence.get("expectedReturnDate") or absence.get("expected_return_date")
        )
    if is_unavailable and kind is None:
        kind = _text(raw.get("type"))
    point = _point(raw)
    return ParsedPlayer(
        fotmob_id=_int(raw.get("id")),
        name=name,
        shirt_number=_int(raw.get("shirtNumber") if "shirtNumber" in raw else raw.get("shirt")),
        is_starter=is_starter,
        is_unavailable=is_unavailable,
        unavailability_type=kind,
        unavailability_label=label,
        expected_return_at=expected,
        uncertain=is_uncertain_absence(label, kind) if is_unavailable else False,
        layout_x=None if point is None else point[0],
        layout_y=None if point is None else point[1],
    )


def _coach_name(raw: object) -> str | None:
    if isinstance(raw, str):
        return _text(raw)
    if isinstance(raw, dict):
        return _text(raw.get("name") or raw.get("shortName"))
    return None


def _point(player: dict) -> tuple[float, float] | None:
    horizontal = player.get("horizontalLayout")
    vertical = player.get("verticalLayout")
    if isinstance(horizontal, dict) and "x" in horizontal and "y" in horizontal:
        x = _float(horizontal.get("x"))
        y = _float(horizontal.get("y"))
        if x is not None and y is not None:
            return x, y
    x = _float(horizontal)
    y = _float(vertical)
    if x is not None and y is not None:
        return x, y
    return None


def _match_nodes(payload: object) -> list[dict]:
    nodes: list[dict] = []

    def walk(value: object) -> None:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and (_team_name(item, "home") or "matches" in item):
                    if _team_name(item, "home"):
                        nodes.append(item)
                    else:
                        walk(item.get("matches"))
                elif isinstance(item, dict):
                    walk(item.get("matches"))
            return
        if not isinstance(value, dict):
            return
        for key in ("matches", "data", "leagues", "response"):
            if key in value:
                walk(value[key])
                return

    walk(payload)
    return nodes


def _team_name(match: dict, side: str) -> str | None:
    for key in (side, f"{side}Team", f"{side}_team"):
        value = match.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            team = value.get("team") if isinstance(value.get("team"), dict) else value
            if isinstance(team, dict):
                name = _text(team.get("name") or team.get("shortName"))
                if name:
                    return name
    return None


def _text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)
    return None


def _float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in ("value", "x", "y"):
            if key in value:
                return _float(value[key])
    return None


def _datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
