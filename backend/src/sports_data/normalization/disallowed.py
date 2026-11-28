"""Gol annullati dal VAR (fuorigioco, fallo, mano): via dagli eventi prima del punteggio.

Il fornitore (API-Football ``/fixtures/events``) racconta un gol annullato in
due modi:

* il gol sparisce dagli eventi alla sincronizzazione successiva e resta solo
  un evento ``Var`` (``"Goal Disallowed - offside"``, ``"Goal cancelled"``...);
* per un po' restano sia il ``Goal`` sia il ``Var`` che lo annulla.

Il primo caso è gestito dal ritiro degli eventi spariti (``fixtures.sync``);
il secondo qui: un ``Var`` di annullamento toglie il gol a cui si riferisce,
così non diventa né riga di cronologia attiva né evento di punteggio (gol,
assist, rigore segnato, autogol). Se il ``Var`` sparisce, o lo segue un
``"Goal confirmed"`` sullo stesso gol, il gol torna.

Abbinamento prudente: stesso calciatore (o, se manca, stessa squadra), il gol
non dopo il ``Var`` e al massimo ``VAR_WINDOW_MINUTES`` prima. Senza un gol
abbinabile non si toglie nulla: meglio un bonus in più segnalato dalle
statistiche che un gol vero cancellato per errore.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

VAR_WINDOW_MINUTES = 5
_GOAL_DETAILS = frozenset({"normal goal", "penalty", "own goal"})


def _text(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _nested_id(row: Mapping[str, Any], key: str) -> int | None:
    block = row.get(key)
    return _as_int(block.get("id")) if isinstance(block, Mapping) else None


def _minute(row: Mapping[str, Any]) -> int | None:
    time_ = row.get("time")
    if not isinstance(time_, Mapping):
        return None
    elapsed = _as_int(time_.get("elapsed"))
    if elapsed is None:
        return None
    return elapsed + (_as_int(time_.get("extra")) or 0)


def is_goal_event(row: Mapping[str, Any]) -> bool:
    return _text(row.get("type")) == "goal" and _text(row.get("detail")) in _GOAL_DETAILS


def is_goal_disallowed_var(row: Mapping[str, Any]) -> bool:
    """``Var`` che annulla un gol: ``Goal Disallowed - …``, ``Goal cancelled``."""
    if _text(row.get("type")) != "var":
        return False
    detail = _text(row.get("detail"))
    return "goal" in detail and ("disallow" in detail or "cancel" in detail)


def is_goal_confirmed_var(row: Mapping[str, Any]) -> bool:
    return _text(row.get("type")) == "var" and _text(row.get("detail")).startswith("goal confirmed")


def disallowed_goal_indexes(raw_events: Sequence[Any]) -> set[int]:
    """Posizioni (in ``raw_events``) dei gol annullati da un evento ``Var``."""
    goals: list[tuple[int, int, int | None, int | None]] = []
    vars_: list[tuple[int, int, bool, int | None, int | None]] = []
    for index, row in enumerate(raw_events):
        if not isinstance(row, Mapping):
            continue
        minute = _minute(row)
        if minute is None:
            continue
        player = _nested_id(row, "player")
        team = _nested_id(row, "team")
        if is_goal_event(row):
            goals.append((index, minute, player, team))
        elif is_goal_disallowed_var(row):
            vars_.append((minute, index, True, player, team))
        elif is_goal_confirmed_var(row):
            vars_.append((minute, index, False, player, team))

    cancelled: set[int] = set()
    for var_minute, _, cancels, var_player, var_team in sorted(vars_):
        in_window = [
            goal
            for goal in goals
            if goal[1] <= var_minute <= goal[1] + VAR_WINDOW_MINUTES
            and ((goal[0] not in cancelled) if cancels else (goal[0] in cancelled))
        ]
        by_player = [
            g
            for g in in_window
            if var_player is not None and g[2] is not None and g[2] == var_player
        ]
        by_team = [
            g for g in in_window if var_team is not None and g[3] is not None and g[3] == var_team
        ]
        matches = by_player or by_team
        if not matches:
            continue
        # Il gol più vicino al VAR (l'ultimo prima), a parità il primo in elenco.
        target = max(matches, key=lambda g: (g[1], -g[0]))[0]
        if cancels:
            cancelled.add(target)
        else:
            cancelled.discard(target)
    return cancelled


#: Parole del fornitore -> motivo in italiano (stesso lessico di ``italianVarEventText`` in
#: ``packages/contracts``). Un motivo non riconosciuto non si inventa: la notifica lo omette.
_REASON_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("offside", "fuorigioco"),
    ("handball", "fallo di mano"),
    ("hand ball", "fallo di mano"),
    ("hand-ball", "fallo di mano"),
    ("foul", "fallo"),
)


def disallowed_reason_it(detail: Any) -> str | None:
    """Motivo in italiano di un ``Var`` di annullamento (``"Goal Disallowed - offside"`` →
    ``"fuorigioco"``), o ``None`` se il fornitore non lo dice o non lo riconosciamo."""
    text = _text(detail)
    for keyword, reason in _REASON_KEYWORDS:
        if keyword in text:
            return reason
    return None


def goal_disallowed_reason(
    raw_events: Sequence[Any],
    *,
    player_provider_id: int | None,
    club_provider_id: int | None,
    minute: int | None,
) -> str | None:
    """Motivo (in italiano) con cui un ``Var`` ha annullato questo gol, se il fornitore lo dice.

    Serve alla notifica «Gol annullato» (gol già sparito dagli eventi, o ancora presente
    accanto al ``Var``): stesso abbinamento prudente di ``disallowed_goal_indexes``, cioè
    stesso calciatore (se no stessa squadra) e ``Var`` al massimo ``VAR_WINDOW_MINUTES`` dopo
    il gol; fra più ``Var`` vale il più vicino. Senza un ``Var`` abbinabile, ``None``.
    """
    if minute is None:
        return None
    candidates: list[tuple[int, bool, Mapping[str, Any]]] = []
    for row in raw_events:
        if not isinstance(row, Mapping) or not is_goal_disallowed_var(row):
            continue
        var_minute = _minute(row)
        if var_minute is None or not minute <= var_minute <= minute + VAR_WINDOW_MINUTES:
            continue
        same_player = (
            player_provider_id is not None and _nested_id(row, "player") == player_provider_id
        )
        same_team = club_provider_id is not None and _nested_id(row, "team") == club_provider_id
        if same_player or same_team:
            candidates.append((var_minute - minute, not same_player, row))
    if not candidates:
        return None
    # Prima chi corrisponde per calciatore, poi il più vicino al gol.
    best = min(candidates, key=lambda item: (item[1], item[0]))
    return disallowed_reason_it(best[2].get("detail"))


def without_disallowed_goals(raw_events: Sequence[Any]) -> list[Any]:
    """Gli eventi senza i gol annullati dal VAR (gli eventi ``Var`` restano)."""
    cancelled = disallowed_goal_indexes(raw_events)
    if not cancelled:
        return list(raw_events)
    return [row for index, row in enumerate(raw_events) if index not in cancelled]
