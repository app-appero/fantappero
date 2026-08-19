"""Official listone and P–D–C–A role assignments (EP04-04)."""

from sports_data.listone.generate import (
    LISTONE_GENERATE_DURATION_SECONDS,
    LISTONE_GENERATE_ENTITIES_TOTAL,
    LISTONE_GENERATE_RUNS_TOTAL,
    LISTONE_UNMAPPED_POSITIONS_TOTAL,
    ListoneGenerateCounters,
    ListoneGenerateResult,
    generate_official_listone,
    get_role_assignment,
    list_role_assignments,
)
from sports_data.listone.mapping import (
    MAPPING_VERSION,
    map_provider_position_to_role,
    normalize_provider_position,
    require_valid_role,
)
from sports_data.listone.models import LeagueRoleOverride, RoleAssignment
from sports_data.listone.overrides import (
    clear_override,
    create_override,
    effective_role_for_athlete,
    get_active_override,
    list_active_overrides,
    override_is_pending,
)
from sports_data.listone.validators import (
    ListoneValidationError,
    compute_override_effective_from_round,
    is_override_effective,
    resolve_effective_role,
    validate_fantasy_role,
)

__all__ = [
    "LISTONE_GENERATE_DURATION_SECONDS",
    "LISTONE_GENERATE_ENTITIES_TOTAL",
    "LISTONE_GENERATE_RUNS_TOTAL",
    "LISTONE_UNMAPPED_POSITIONS_TOTAL",
    "MAPPING_VERSION",
    "LeagueRoleOverride",
    "ListoneGenerateCounters",
    "ListoneGenerateResult",
    "ListoneValidationError",
    "RoleAssignment",
    "clear_override",
    "compute_override_effective_from_round",
    "create_override",
    "effective_role_for_athlete",
    "generate_official_listone",
    "get_active_override",
    "get_role_assignment",
    "is_override_effective",
    "list_active_overrides",
    "list_role_assignments",
    "map_provider_position_to_role",
    "normalize_provider_position",
    "override_is_pending",
    "require_valid_role",
    "resolve_effective_role",
    "validate_fantasy_role",
]
