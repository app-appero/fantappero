"""Validation rules for listone roles and league overrides (EP04-04)."""

from __future__ import annotations

from database.enums import FantasyRole, LeagueState
from sports_data.listone.mapping import require_valid_role

PRE_AUCTION_STATES = frozenset(
    {
        LeagueState.DRAFT,
        LeagueState.CONFIGURING,
        LeagueState.AUCTION,
    }
)
POST_START_STATES = frozenset({LeagueState.ACTIVE})
LOCKED_OVERRIDE_STATES = frozenset({LeagueState.CONCLUDED, LeagueState.ARCHIVED})


class ListoneValidationError(Exception):
    """Domain validation failure with stable error code."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def validate_fantasy_role(role: FantasyRole | str) -> FantasyRole:
    try:
        return require_valid_role(role)
    except ValueError as exc:
        raise ListoneValidationError(
            "Il ruolo deve essere uno tra P, D, C, A.",
            code="invalid_fantasy_role",
        ) from exc


def compute_override_effective_from_round(
    *,
    league_state: LeagueState,
    current_round: int | None,
) -> int | None:
    """Return effective_from_round for a new override.

    Pre-asta (draft/configuring/auction): immediate (``None`` = from auction/start).
    Post-avvio (active): next round (current_round + 1).
    """
    if league_state in LOCKED_OVERRIDE_STATES:
        raise ListoneValidationError(
            "Non puoi modificare i ruoli in una lega conclusa o archiviata.",
            code="league_role_override_locked",
        )
    if league_state in PRE_AUCTION_STATES:
        return None
    if league_state in POST_START_STATES:
        round_number = 0 if current_round is None else current_round
        if round_number < 0:
            raise ListoneValidationError(
                "Il turno corrente non può essere negativo.",
                code="invalid_current_round",
            )
        return round_number + 1
    raise ListoneValidationError(
        "Stato lega non valido per override di ruolo.",
        code="league_role_override_locked",
    )


def is_override_effective(
    *,
    effective_from_round: int | None,
    current_round: int,
) -> bool:
    """Whether an override applies at ``current_round`` (1-based league turn)."""
    if current_round < 0:
        return False
    if effective_from_round is None:
        return True
    return effective_from_round <= current_round


def resolve_effective_role(
    *,
    official_role: FantasyRole,
    override_role: FantasyRole | None,
    override_effective_from_round: int | None,
    current_round: int,
) -> FantasyRole:
    """Official role unless a pending override has already taken effect."""
    if override_role is None:
        return official_role
    if is_override_effective(
        effective_from_round=override_effective_from_round,
        current_round=current_round,
    ):
        return override_role
    return official_role
