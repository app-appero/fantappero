"""Domain validators for the live/ascending auction mode (EP08-09)."""

from __future__ import annotations

import random
from collections.abc import Sequence

from auth.exceptions import ValidationAuthError

# P→D→C→A: same canonical role order used league-wide (fantasy_teams.composition
# .ROLE_LABEL_IT, RosterCompositionLimits fields, FantasyRole enum declaration).
_ROLE_SORT_ORDER: dict[str, int] = {"P": 0, "D": 1, "C": 2, "A": 3}


def validate_live_session_config(
    *,
    min_increment_credits: int,
    soft_close_seconds: int,
    lot_duration_seconds: int,
) -> None:
    if min_increment_credits < 1:
        raise ValidationAuthError(
            "L'incremento minimo deve essere di almeno 1 credito.",
            code="invalid_min_increment",
        )
    if not (5 <= soft_close_seconds <= 120):
        raise ValidationAuthError(
            "La finestra di soft-close deve essere tra 5 e 120 secondi.",
            code="invalid_soft_close_seconds",
        )
    if not (10 <= lot_duration_seconds <= 300):
        raise ValidationAuthError(
            "La durata del lotto deve essere tra 10 e 300 secondi.",
            code="invalid_lot_duration",
        )


def compute_minimum_next_amount(
    *,
    current_amount_credits: int,
    has_leader: bool,
    min_increment_credits: int,
) -> int:
    """Single authoritative source for the "next valid raise" rule (EP08-09).

    The first raise on an unsold lot must be at least ``min_increment_credits``;
    every raise after that must beat the current amount by at least that same
    increment. Mirrored client-side (``packages/contracts/src/liveAuction.ts``)
    for instant UI feedback only — this function is what the server enforces.
    """
    if not has_leader:
        return min_increment_credits
    return current_amount_credits + min_increment_credits


def validate_raise_amount(
    *,
    amount_credits: int,
    current_amount_credits: int,
    has_leader: bool,
    min_increment_credits: int,
) -> None:
    minimum = compute_minimum_next_amount(
        current_amount_credits=current_amount_credits,
        has_leader=has_leader,
        min_increment_credits=min_increment_credits,
    )
    if amount_credits < minimum:
        raise ValidationAuthError(
            f"Il rilancio deve essere di almeno {minimum} crediti.",
            code="market_live_raise_stale",
        )


def validate_not_current_leader(*, current_leader_team_id: object | None, team_id: object) -> None:
    if current_leader_team_id is not None and current_leader_team_id == team_id:
        raise ValidationAuthError(
            "Sei già il miglior offerente su questo lotto.",
            code="market_live_already_leader",
        )


def sort_athletes_alphabetical_by_role(
    athletes: Sequence[tuple[str, str, str]],
) -> list[str]:
    """Order free-agent athletes for the ``ALPHABETICAL_BY_ROLE`` nomination queue.

    ``athletes`` is a sequence of ``(athlete_id, role, canonical_name)`` triples.
    Sorted P→D→C→A, then alphabetically (case/locale-insensitive) by name inside
    each role group. Unknown/unresolved role codes sort after A, alphabetically
    among themselves, rather than raising — a listone gap should never block
    queue generation for the rest of the league.
    """
    ordered = sorted(
        athletes,
        key=lambda row: (
            _ROLE_SORT_ORDER.get(row[1], len(_ROLE_SORT_ORDER)),
            row[2].casefold(),
        ),
    )
    return [athlete_id for athlete_id, _role, _name in ordered]


def shuffle_athlete_ids(
    athlete_ids: Sequence[str], *, rng: random.Random | None = None
) -> list[str]:
    """Order free-agent athletes for the ``RANDOM`` nomination queue.

    Drawn once at session creation, same principle as a real live auction
    shuffling the deck before play starts — never reshuffled afterwards.
    ``rng`` is injectable so tests can assert a deterministic order; production
    call sites pass no ``rng`` (a fresh, unseeded ``random.Random()``).
    """
    pool = list(athlete_ids)
    (rng or random.Random()).shuffle(pool)
    return pool


def compute_turn_team_index(*, nominated_count: int, team_count: int) -> int | None:
    """Which position in the ``TURN_BASED`` rotation gets to call the next lot.

    Rotates strictly by how many lots have already been opened in the session
    so far (``nominated_count``), regardless of their outcome — a lot that got
    no raises, or was cancelled, still consumes that team's turn, exactly like
    a real live auction where calling a player uses up your turn whether or
    not anybody bids. Returns ``None`` if there is no team to take a turn.
    """
    if team_count <= 0:
        return None
    return nominated_count % team_count

