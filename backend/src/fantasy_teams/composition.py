"""Roster composition evaluation against league rules (EP05-05 / FR-ROS-02)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from database.enums import FantasyRole, RosterCompositionStatus
from leagues.validators import MIN_COMPETITIONS

# FR-ROS-02: at least three competitions represented in a complete roster.
MIN_ROSTER_COMPETITIONS = MIN_COMPETITIONS

ROLE_LIMIT_ATTR: Mapping[FantasyRole, str] = {
    FantasyRole.P: "goalkeepers",
    FantasyRole.D: "defenders",
    FantasyRole.C: "midfielders",
    FantasyRole.A: "forwards",
}

ROLE_LABEL_IT: Mapping[FantasyRole, str] = {
    FantasyRole.P: "portieri",
    FantasyRole.D: "difensori",
    FantasyRole.C: "centrocampisti",
    FantasyRole.A: "attaccanti",
}


@dataclass(frozen=True)
class RosterCompositionLimits:
    roster_size: int
    goalkeepers: int
    defenders: int
    midfielders: int
    forwards: int

    def for_role(self, role: FantasyRole) -> int:
        return int(getattr(self, ROLE_LIMIT_ATTR[role]))

    def as_role_map(self) -> dict[FantasyRole, int]:
        return {role: self.for_role(role) for role in FantasyRole}


@dataclass(frozen=True)
class CompositionIssue:
    code: str
    message: str


@dataclass(frozen=True)
class RosterCompositionReport:
    limits: RosterCompositionLimits
    counts: dict[str, int]
    filled_slots: int
    competition_count: int
    status: RosterCompositionStatus
    issues: tuple[CompositionIssue, ...]
    require_complete: bool

    @property
    def is_valid_for_season_start(self) -> bool:
        return self.status == RosterCompositionStatus.VALIDATED and not self.issues


def limits_from_rules(
    *,
    roster_size: int,
    goalkeepers: int,
    defenders: int,
    midfielders: int,
    forwards: int,
) -> RosterCompositionLimits:
    return RosterCompositionLimits(
        roster_size=roster_size,
        goalkeepers=goalkeepers,
        defenders=defenders,
        midfielders=midfielders,
        forwards=forwards,
    )


def count_roles(roles: Iterable[FantasyRole | None]) -> dict[FantasyRole, int]:
    counter: Counter[FantasyRole] = Counter()
    for role in roles:
        if role is not None:
            counter[role] += 1
    return {role: int(counter.get(role, 0)) for role in FantasyRole}


def evaluate_roster_composition(
    *,
    limits: RosterCompositionLimits,
    roles: Sequence[FantasyRole | None],
    competition_ids: Iterable[UUID],
    require_complete: bool,
    unresolved_role_count: int = 0,
) -> RosterCompositionReport:
    """Evaluate P–D–C–A quotas and competition diversity.

    During auction ``require_complete=False``: incomplete rosters are allowed, but
    over-quota and unresolved roles remain invalid.
    At season start ``require_complete=True``: exact totals and ≥3 competitions.
    """
    filled = sum(1 for role in roles if role is not None) + unresolved_role_count
    role_counts = count_roles(roles)
    competition_count = len({cid for cid in competition_ids})
    issues: list[CompositionIssue] = []

    if unresolved_role_count > 0:
        issues.append(
            CompositionIssue(
                code="role_unresolved",
                message=(
                    f"{unresolved_role_count} calciatore/i senza ruolo listone "
                    "risolvibile (P–D–C–A)."
                ),
            )
        )

    for role in FantasyRole:
        limit = limits.for_role(role)
        current = role_counts[role]
        if current > limit:
            issues.append(
                CompositionIssue(
                    code="role_quota_exceeded",
                    message=(
                        f"Troppi {ROLE_LABEL_IT[role]}: {current} su massimo {limit}."
                    ),
                )
            )

    if require_complete:
        if filled != limits.roster_size:
            issues.append(
                CompositionIssue(
                    code="roster_incomplete",
                    message=(
                        f"Rosa incompleta: {filled}/{limits.roster_size} calciatori."
                    ),
                )
            )
        for role in FantasyRole:
            limit = limits.for_role(role)
            current = role_counts[role]
            if current < limit:
                issues.append(
                    CompositionIssue(
                        code="role_quota_underfilled",
                        message=(
                            f"Servono {limit} {ROLE_LABEL_IT[role]}, ne risultano {current}."
                        ),
                    )
                )
        if competition_count < MIN_ROSTER_COMPETITIONS:
            issues.append(
                CompositionIssue(
                    code="insufficient_roster_competitions",
                    message=(
                        f"La rosa deve rappresentare almeno {MIN_ROSTER_COMPETITIONS} "
                        f"campionati (attuali: {competition_count})."
                    ),
                )
            )

    hard_invalid = any(
        issue.code
        in {
            "role_quota_exceeded",
            "role_unresolved",
            "roster_incomplete",
            "role_quota_underfilled",
            "insufficient_roster_competitions",
        }
        for issue in issues
    )

    exact_roles = all(role_counts[role] == limits.for_role(role) for role in FantasyRole)
    complete = (
        filled == limits.roster_size
        and exact_roles
        and unresolved_role_count == 0
        and competition_count >= MIN_ROSTER_COMPETITIONS
        and not any(issue.code == "role_quota_exceeded" for issue in issues)
    )

    if hard_invalid and require_complete:
        status = RosterCompositionStatus.INVALID
    elif any(issue.code in {"role_quota_exceeded", "role_unresolved"} for issue in issues):
        status = RosterCompositionStatus.INVALID
    elif complete:
        status = RosterCompositionStatus.VALIDATED
    else:
        status = RosterCompositionStatus.INCOMPLETE

    counts = {
        "P": role_counts[FantasyRole.P],
        "D": role_counts[FantasyRole.D],
        "C": role_counts[FantasyRole.C],
        "A": role_counts[FantasyRole.A],
    }
    return RosterCompositionReport(
        limits=limits,
        counts=counts,
        filled_slots=filled,
        competition_count=competition_count,
        status=status,
        issues=tuple(issues),
        require_complete=require_complete,
    )


def would_exceed_role_quota(
    *,
    limits: RosterCompositionLimits,
    current_roles: Sequence[FantasyRole | None],
    new_role: FantasyRole,
    replacing_role: FantasyRole | None = None,
) -> bool:
    """True if adding ``new_role`` (optionally replacing another) exceeds the limit."""
    counts = count_roles(current_roles)
    if replacing_role is not None:
        counts[replacing_role] = max(0, counts[replacing_role] - 1)
    counts[new_role] = counts[new_role] + 1
    return counts[new_role] > limits.for_role(new_role)
