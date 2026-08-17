"""Domain validators for fantasy teams and roster exclusivity (EP05-01)."""

from __future__ import annotations

from uuid import UUID

from auth.exceptions import ValidationAuthError


def validate_slot_index(*, slot_index: int, roster_size: int) -> None:
    if slot_index < 0 or slot_index >= roster_size:
        raise ValidationAuthError(
            f"Lo slot deve essere compreso tra 0 e {roster_size - 1}.",
            code="invalid_slot_index",
        )


def validate_athlete_not_owned_in_league(
    *,
    existing_team_id: UUID | None,
    target_team_id: UUID,
) -> None:
    """Reject assignment when the athlete already belongs to another team in the league."""
    if existing_team_id is not None and existing_team_id != target_team_id:
        raise ValidationAuthError(
            "Il calciatore appartiene già a un'altra squadra in questa lega.",
            code="athlete_already_owned",
        )


def validate_purchase_credits(purchase_credits: int) -> int:
    if purchase_credits < 0:
        raise ValidationAuthError(
            "Il credito di acquisto non può essere negativo.",
            code="invalid_purchase_credits",
        )
    return purchase_credits


def validate_credit_amount_nonzero(amount: int) -> int:
    if amount == 0:
        raise ValidationAuthError(
            "L'importo del movimento deve essere diverso da zero.",
            code="invalid_credit_amount",
        )
    return amount


def validate_ledger_balance_non_negative(balance: int) -> int:
    if balance < 0:
        raise ValidationAuthError(
            "Il saldo crediti non può diventare negativo.",
            code="insufficient_credits",
        )
    return balance


def validate_transaction_id(transaction_id: str) -> str:
    cleaned = transaction_id.strip()
    if not cleaned or len(cleaned) > 128:
        raise ValidationAuthError(
            "Identificativo di transazione non valido.",
            code="invalid_transaction_id",
        )
    return cleaned
