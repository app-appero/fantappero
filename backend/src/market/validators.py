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


def validate_release_athlete_required(release_athlete_id: UUID | None) -> UUID:
    """Every waiver bid must name the roster player to release (FR-MKT-01)."""
    if release_athlete_id is None:
        raise ValidationAuthError(
            "Indica il calciatore da svincolare per completare l'offerta.",
            code="release_athlete_required",
        )
    return release_athlete_id


def validate_release_athlete_not_allowed(release_athlete_id: str | None) -> None:
    """Auction bids never name a player to release — that is waiver-only."""
    if release_athlete_id is not None:
        raise ValidationAuthError(
            "L'asta iniziale non prevede lo svincolo di un calciatore.",
            code="release_athlete_not_allowed",
        )


def validate_release_athlete_owned_by_team(*, owner_team_id: UUID | None, team_id: UUID) -> None:
    if owner_team_id != team_id:
        raise ValidationAuthError(
            "Il calciatore da svincolare non è nella tua rosa.",
            code="release_athlete_not_owned",
        )


def validate_slot_has_athlete(athlete_id: UUID | None) -> UUID:
    """A voluntary release needs an occupied slot (EP08-04 / FR-MKT-02)."""
    if athlete_id is None:
        raise ValidationAuthError(
            "Lo slot è già libero.",
            code="release_slot_empty",
        )
    return athlete_id


def compute_release_refund(*, purchase_credits: int, refund_percent: int) -> int:
    """Rounding rule for svincolo refunds: integer floor division (unique and public).

    ``refund = floor(purchase_credits * refund_percent / 100)``. Documented once here
    per FR-MKT-02 ("la regola di arrotondamento dei crediti deve essere unica e pubblica").
    """
    return (purchase_credits * refund_percent) // 100
