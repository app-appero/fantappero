"""Domain validators for the sealed-bid market session (EP08-01)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

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


def validate_bid_targets_session_athlete(
    *, target_athlete_id: UUID | None, athlete_id: UUID
) -> None:
    """Tiebreak sessions restrict bidding to the single contested athlete (EP08-02)."""
    if target_athlete_id is not None and target_athlete_id != athlete_id:
        raise ValidationAuthError(
            "Questo spareggio riguarda soltanto il calciatore conteso.",
            code="market_bid_wrong_athlete",
        )


def validate_team_eligible_for_session(
    *, eligible_team_ids: list[str] | None, fantasy_team_id: UUID
) -> None:
    """Tiebreak sessions restrict bidding to the teams that tied (EP08-02)."""
    if eligible_team_ids is not None and str(fantasy_team_id) not in eligible_team_ids:
        raise ValidationAuthError(
            "La tua squadra non partecipa a questo spareggio.",
            code="market_team_not_eligible",
        )
