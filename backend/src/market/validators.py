"""Domain validators for the sealed-bid market session (EP08-01)."""

from __future__ import annotations

from datetime import datetime

from auth.exceptions import ValidationAuthError


def validate_session_window(*, opens_at: datetime, closes_at: datetime) -> None:
    if closes_at <= opens_at:
        raise ValidationAuthError(
            "La scadenza della sessione deve essere successiva all'apertura.",
            code="invalid_session_window",
        )


def validate_bid_amount(amount_credits: int) -> int:
    if amount_credits < 1:
        raise ValidationAuthError(
            "L'offerta deve essere di almeno 1 credito.",
            code="invalid_bid_amount",
        )
    return amount_credits


def validate_amount_within_balance(*, amount_credits: int, balance: int) -> None:
    if amount_credits > balance:
        raise ValidationAuthError(
            "L'offerta supera il saldo crediti disponibile.",
            code="insufficient_credits",
        )


def validate_team_has_free_slot(*, has_free_slot: bool) -> None:
    if not has_free_slot:
        raise ValidationAuthError(
            "La rosa non ha slot liberi per accogliere un nuovo calciatore.",
            code="roster_full",
        )


def validate_athlete_is_free_agent(*, owner_team_id: object | None) -> None:
    if owner_team_id is not None:
        raise ValidationAuthError(
            "Il calciatore appartiene già a una squadra della lega.",
            code="athlete_already_owned",
        )
