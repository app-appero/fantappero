"""Validità strutturale di una formazione prevista.

Separata dalla validità sportiva: un JSON ben formato con undici nomi può
comunque non corrispondere alla rosa. Qui si misurano solo controlli
espliciti. Nessuna percentuale inventata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sports_data.predicted.parse import ParsedPlayer, ParsedSide, formation_is_valid

RELIABILITY_VALIDATED = "validated"
RELIABILITY_PARTIAL = "partially_validated"
RELIABILITY_UNVERIFIED = "unverified"
RELIABILITY_REJECTED = "rejected"

_HARD_ABSENCE = {"injury", "suspension", "suspended", "red", "red_card", "redcard"}
USABLE_RELIABILITY = frozenset({RELIABILITY_VALIDATED, RELIABILITY_PARTIAL})


@dataclass(frozen=True)
class SideCheck:
    starter_count: int
    duplicate: bool
    formation_ok: bool
    starter_also_unavailable: bool
    mapped_starters: int


@dataclass(frozen=True)
class Reliability:
    code: str
    warnings: tuple[str, ...]


def starter_key(player: ParsedPlayer) -> str:
    if player.fotmob_id is not None:
        return f"id:{player.fotmob_id}"
    return f"name:{player.name.strip().lower()}"


def side_starters(side: ParsedSide | None) -> list[ParsedPlayer]:
    if side is None:
        return []
    unavailable = {starter_key(player) for player in side.players if player.is_unavailable}
    chosen: list[ParsedPlayer] = []
    seen: set[str] = set()
    for player in side.players:
        if not player.is_starter:
            continue
        key = starter_key(player)
        if key in unavailable or key in seen:
            continue
        seen.add(key)
        chosen.append(player)
    return chosen


def check_side(
    side: ParsedSide | None,
    *,
    mapped_starter_keys: set[str],
) -> SideCheck:
    if side is None:
        return SideCheck(0, False, False, False, 0)
    unavailable = {starter_key(player) for player in side.players if player.is_unavailable}
    raw_starters = [player for player in side.players if player.is_starter]
    keys = [starter_key(player) for player in raw_starters]
    overlap = any(key in unavailable for key in keys)
    unique = side_starters(side)
    return SideCheck(
        starter_count=len(unique),
        duplicate=len(keys) != len(set(keys)),
        formation_ok=formation_is_valid(side.formation),
        starter_also_unavailable=overlap,
        mapped_starters=sum(1 for player in unique if starter_key(player) in mapped_starter_keys),
    )


def classify_reliability(
    home: SideCheck,
    away: SideCheck,
    *,
    player_count: int,
    extra_warnings: tuple[str, ...] = (),
) -> Reliability:
    warnings = list(extra_warnings)
    if player_count <= 0:
        warnings.append("empty")
        return Reliability(RELIABILITY_REJECTED, tuple(dict.fromkeys(warnings)))

    for label, side in (("home", home), ("away", away)):
        if side.starter_count != 11:
            warnings.append(f"{label}_starter_count")
        if side.duplicate:
            warnings.append(f"{label}_duplicate")
        if not side.formation_ok:
            warnings.append(f"{label}_formation")
        if side.starter_also_unavailable:
            warnings.append(f"{label}_starter_unavailable")

    structural = (
        home.starter_count == 11
        and away.starter_count == 11
        and home.formation_ok
        and away.formation_ok
        and not home.duplicate
        and not away.duplicate
        and not home.starter_also_unavailable
        and not away.starter_also_unavailable
    )
    mapped = home.mapped_starters + away.mapped_starters
    total = home.starter_count + away.starter_count
    if structural and total > 0 and mapped == total:
        code = RELIABILITY_VALIDATED
    elif mapped == 0:
        code = RELIABILITY_UNVERIFIED
    else:
        code = RELIABILITY_PARTIAL
    return Reliability(code, tuple(dict.fromkeys(warnings)))


def blocks_selection(
    *,
    mapped: bool,
    unavailability_type: str | None,
    uncertain: bool,
    expected_return_at: datetime | None,
    kickoff_at: datetime | None,
) -> bool:
    """Blocca la scelta in formazione solo per un'assenza dura e già collegata alla rosa."""
    if not mapped or uncertain:
        return False
    kind = (unavailability_type or "").strip().lower()
    if kind not in _HARD_ABSENCE:
        return False
    if expected_return_at is not None and kickoff_at is not None:
        if expected_return_at <= kickoff_at:
            return False
    return True


def grids_for_starters(players: list[ParsedPlayer]) -> dict[str, str]:
    """``riga:colonna`` con riga 1 = portiere, se le coordinate bastano a separare le linee."""
    placed = [
        player
        for player in players
        if player.layout_x is not None and player.layout_y is not None
    ]
    if len(placed) != len(players) or len(placed) < 2:
        return {}
    ordered = sorted(placed, key=lambda player: (player.layout_y or 0, player.layout_x or 0))
    ys = [player.layout_y or 0 for player in ordered]
    span = max(ys) - min(ys)
    if span <= 0:
        return {}
    gap = max(span * 0.12, 1.0)
    bands: list[list[ParsedPlayer]] = [[ordered[0]]]
    for player in ordered[1:]:
        if (player.layout_y or 0) - (bands[-1][-1].layout_y or 0) > gap:
            bands.append([player])
        else:
            bands[-1].append(player)
    if len(bands) < 2:
        return {}
    # Il portiere è la fascia estrema da un solo giocatore. Se sta sul valore y
    # più alto, quelle y crescono verso la propria porta e vanno rovesciate.
    edge_low = len(bands[0]) == 1
    edge_high = len(bands[-1]) == 1
    if edge_high and not edge_low:
        bands.reverse()
    elif edge_high and edge_low:
        # Entrambe le estremità hanno un uomo solo: la fascia più isolata è il portiere.
        low_gap = (bands[1][0].layout_y or 0) - (bands[0][0].layout_y or 0)
        high_gap = (bands[-1][0].layout_y or 0) - (bands[-2][0].layout_y or 0)
        if high_gap > low_gap:
            bands.reverse()
    grids: dict[str, str] = {}
    for row_index, band in enumerate(bands, start=1):
        for column, player in enumerate(sorted(band, key=lambda item: item.layout_x or 0), start=1):
            grids[starter_key(player)] = f"{row_index}:{column}"
    return grids
