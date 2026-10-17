"""Lettura difensiva delle risposte di ``GET /players/lineups`` (Soccer-Oracle).

Contratto in docs/player_identity.md su romy1992/ia_predict_soccer
(branch ccr-f82a865a-m1lzbd, non ancora deployato). Come per FotMob in
``parse.py``, un payload malformato produce una formazione vuota, non
un'eccezione: il job non deve bloccarsi per una risposta inattesa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

_UNCERTAIN_PHRASES = ("doubtful", "dubbio", "uncertain", "unconfirmed", "da confermare")


@dataclass(frozen=True)
class OraclePlayer:
    name: str
    api_sports_id: int | None
    fotmob_id: int | None
    identity_id: str | None
    mapped: bool
    confidence: float
    shirt_number: int | None
    absence_type: str | None
    absence_label: str | None
    absence_expected_return_at: datetime | None
    absence_uncertain: bool


@dataclass(frozen=True)
class OracleTeam:
    team_api_id: int | None
    formation: str | None
    starters: tuple[OraclePlayer, ...]
    bench: tuple[OraclePlayer, ...]
    unavailable: tuple[OraclePlayer, ...]


@dataclass(frozen=True)
class OracleFixtureLineup:
    lineup_type: str | None  # "official" | "predicted" | None
    source: str | None  # "api_sports" | "fotmob" | None
    unmapped_starters: int | None
    teams: tuple[OracleTeam, ...]


def parse_oracle_lineups_response(payload: object) -> dict[int, OracleFixtureLineup]:
    """``fixture_id`` (ID API-Sports) -> formazione. Voci illeggibili vengono scartate."""
    result: dict[int, OracleFixtureLineup] = {}
    if not isinstance(payload, dict):
        return result
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list):
        return result
    for item in fixtures:
        if not isinstance(item, dict):
            continue
        fixture_id = _int(item.get("fixture_id"))
        if fixture_id is None:
            continue
        result[fixture_id] = _parse_fixture_lineup(item)
    return result


def _parse_fixture_lineup(item: dict) -> OracleFixtureLineup:
    lineup_type = _text(item.get("lineup_type"))
    if lineup_type not in {"official", "predicted"}:
        lineup_type = None
    teams_raw = item.get("teams")
    teams: list[OracleTeam] = []
    if isinstance(teams_raw, list):
        for team_raw in teams_raw:
            team = _parse_team(team_raw)
            if team is not None:
                teams.append(team)
    return OracleFixtureLineup(
        lineup_type=lineup_type,
        source=_text(item.get("source")),
        unmapped_starters=_int(item.get("unmapped_starters")),
        teams=tuple(teams),
    )


def _parse_team(raw: object) -> OracleTeam | None:
    if not isinstance(raw, dict):
        return None
    return OracleTeam(
        team_api_id=_int(raw.get("team_api_id")),
        formation=_text(raw.get("formation")),
        starters=_parse_players(raw.get("starters")),
        bench=_parse_players(raw.get("bench")),
        unavailable=_parse_players(raw.get("unavailable")),
    )


def _parse_players(raw: object) -> tuple[OraclePlayer, ...]:
    if not isinstance(raw, list):
        return ()
    players: list[OraclePlayer] = []
    for item in raw:
        player = _parse_player(item)
        if player is not None:
            players.append(player)
    return tuple(players)


def _parse_player(raw: object) -> OraclePlayer | None:
    if not isinstance(raw, dict):
        return None
    name = _text(raw.get("name"))
    if not name:
        return None
    absence = raw.get("absence") if isinstance(raw.get("absence"), dict) else None
    absence_type = _text(absence.get("type")) if absence else None
    absence_label = _text(absence.get("expected_return")) if absence else None
    expected_at = _datetime(absence.get("expected_return_date")) if absence else None
    certainty = _text(absence.get("certainty")) if absence else None
    confidence = _float(raw.get("confidence"))
    return OraclePlayer(
        name=name,
        api_sports_id=_int(raw.get("api_sports_id")),
        fotmob_id=_int(raw.get("fotmob_id")),
        identity_id=_text(raw.get("identity_id")),
        mapped=bool(raw.get("mapped")),
        confidence=confidence if confidence is not None else 0.0,
        shirt_number=_int(raw.get("shirt_number")),
        absence_type=absence_type,
        absence_label=absence_label,
        absence_expected_return_at=expected_at,
        absence_uncertain=_is_uncertain(absence_label, certainty),
    )


def _is_uncertain(label: str | None, certainty: str | None) -> bool:
    blob = f"{label or ''} {certainty or ''}".lower()
    return any(phrase in blob for phrase in _UNCERTAIN_PHRASES)


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
        if stripped.lstrip("-").isdigit():
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
    return None


def _datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
