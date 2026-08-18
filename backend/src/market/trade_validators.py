"""Domain validators for trade proposals (EP08-05 / FR-MKT-03)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from auth.exceptions import ValidationAuthError


def validate_trades_enabled(*, allow_trades: bool) -> None:
    if not allow_trades:
        raise ValidationAuthError(
            "Gli scambi sono disattivati dall'amministratore per questa lega.",
            code="trades_disabled",
        )


def validate_trade_expiry(expires_at: datetime, *, now: datetime) -> None:
    if expires_at <= now:
        raise ValidationAuthError(
            "La scadenza della proposta deve essere futura.",
            code="invalid_trade_expiry",
        )


def validate_distinct_teams(*, proposer_team_id: UUID, recipient_team_id: UUID) -> None:
    if proposer_team_id == recipient_team_id:
        raise ValidationAuthError(
            "Non puoi proporre uno scambio alla tua stessa squadra.",
            code="trade_same_team",
        )


def parse_athlete_ids(raw: list[str], *, field: str) -> list[UUID]:
    try:
        parsed = [UUID(value) for value in raw]
    except ValueError as exc:
        raise ValidationAuthError(
            f"Identificativo calciatore non valido in {field}.",
            code="invalid_athlete_id",
        ) from exc
    if len(set(parsed)) != len(parsed):
        raise ValidationAuthError(
            f"Calciatori duplicati in {field}.",
            code="duplicate_athlete_id",
        )
    return parsed


def validate_trade_sides_not_empty(
    *,
    offered_athlete_ids: list[UUID],
    offered_credits: int,
    requested_athlete_ids: list[UUID],
    requested_credits: int,
) -> None:
    if not offered_athlete_ids and offered_credits <= 0:
        raise ValidationAuthError(
            "Devi offrire almeno un calciatore o dei crediti.",
            code="trade_offer_empty",
        )
    if not requested_athlete_ids and requested_credits <= 0:
        raise ValidationAuthError(
            "Devi richiedere almeno un calciatore o dei crediti.",
            code="trade_request_empty",
        )


def validate_no_athlete_overlap(
    *, offered_athlete_ids: list[UUID], requested_athlete_ids: list[UUID]
) -> None:
    overlap = set(offered_athlete_ids) & set(requested_athlete_ids)
    if overlap:
        raise ValidationAuthError(
            "Un calciatore non può essere sia offerto che richiesto nella stessa proposta.",
            code="trade_athlete_overlap",
        )


def validate_athletes_owned_by_team(
    *, athlete_ids: list[UUID], owned_athlete_ids: set[UUID], team_label: str
) -> None:
    missing = set(athlete_ids) - owned_athlete_ids
    if missing:
        raise ValidationAuthError(
            f"Uno o più calciatori non sono nella rosa {team_label}.",
            code="trade_athlete_not_owned",
        )


def validate_offered_credits_within_balance(*, offered_credits: int, balance: int) -> None:
    if offered_credits > balance:
        raise ValidationAuthError(
            "I crediti offerti superano il saldo disponibile.",
            code="insufficient_credits",
        )
