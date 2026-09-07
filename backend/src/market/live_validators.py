"""Domain validators for the live/ascending auction mode (EP08-09)."""

from __future__ import annotations

from auth.exceptions import ValidationAuthError


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
