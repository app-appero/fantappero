"""Validation rules for roster sync (EP04-03)."""

from __future__ import annotations

# Loan / N/A non affidabili per auto-svincolo (matrice EP00-01 §3.10, OQ-12).
_TRANSFER_TYPES_REQUIRING_REVIEW = frozenset({"loan", "n/a"})


def transfer_requires_admin_review(transfer_type: str | None) -> bool:
    """Return True when transfer type needs manual review before market actions."""
    if not transfer_type or not transfer_type.strip():
        return True
    return transfer_type.strip().lower() in _TRANSFER_TYPES_REQUIRING_REVIEW


def build_transfer_provider_key(
    *,
    athlete_provider_id: int,
    transfer_date: str,
    from_club_provider_id: int | None,
    to_club_provider_id: int | None,
    transfer_type: str,
) -> str:
    """Stable idempotency key for a provider transfer row."""
    return (
        f"{athlete_provider_id}:{transfer_date}:"
        f"{from_club_provider_id or 0}:{to_club_provider_id or 0}:{transfer_type.strip()}"
    )
