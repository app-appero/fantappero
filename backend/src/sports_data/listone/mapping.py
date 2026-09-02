"""Versioned provider position → FantApperò role mapping (EP04-04 / OQ-01)."""

from __future__ import annotations

from database.enums import FantasyRole

# Bump when the closed mapping table changes (idempotent regenerate).
MAPPING_VERSION = "v1.0.0"

# Canonical API-Football positions observed on MVP squad fixtures + short codes
# used by Rating Beta offline corpus (G/D/M/F).
_POSITION_TO_ROLE: dict[str, FantasyRole] = {
    "goalkeeper": FantasyRole.P,
    "g": FantasyRole.P,
    "gk": FantasyRole.P,
    "keeper": FantasyRole.P,
    "defensor": FantasyRole.D,
    "defender": FantasyRole.D,
    "d": FantasyRole.D,
    "defence": FantasyRole.D,
    "defense": FantasyRole.D,
    "midfielder": FantasyRole.C,
    "m": FantasyRole.C,
    "midfield": FantasyRole.C,
    "attacker": FantasyRole.A,
    "forward": FantasyRole.A,
    "f": FantasyRole.A,
    "striker": FantasyRole.A,
}


def normalize_provider_position(raw: str | None) -> str | None:
    """Normalize provider position text for lookup (case/space insensitive)."""
    if raw is None:
        return None
    text = " ".join(str(raw).strip().lower().split())
    return text or None


def map_provider_position_to_role(raw: str | None) -> FantasyRole | None:
    """Map a provider position string to P/D/C/A, or None if unmapped."""
    key = normalize_provider_position(raw)
    if key is None:
        return None
    if key in _POSITION_TO_ROLE:
        return _POSITION_TO_ROLE[key]
    # Accept already-canonical role codes.
    if key in {"p", "d", "c", "a"}:
        return FantasyRole(key.upper())
    return None


def require_valid_role(role: FantasyRole | str) -> FantasyRole:
    """Validate and coerce a fantasy role code."""
    if isinstance(role, FantasyRole):
        return role
    text = str(role).strip().upper()
    try:
        return FantasyRole(text)
    except ValueError as exc:
        raise ValueError(f"Ruolo non valido: {role!r}") from exc
