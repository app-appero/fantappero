"""Quando una lettura della rosa deve riallineare stato salvato e flag (QA 20/11)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from database.enums import FantasyRole, RosterCompositionStatus
from fantasy_teams.composition import evaluate_roster_composition, limits_from_rules
from fantasy_teams.composition_service import EffectiveAthleteRole, composition_needs_refresh

LIMITS = limits_from_rules(roster_size=4, goalkeepers=1, defenders=1, midfielders=1, forwards=1)
ROLES = (FantasyRole.P, FantasyRole.D, FantasyRole.C, FantasyRole.A)


def _team(
    roles: list[FantasyRole | None],
    *,
    status: RosterCompositionStatus,
    flagged: set[int] = frozenset(),  # type: ignore[assignment]
    empty_slots: int = 0,
):
    slots = [
        SimpleNamespace(slot_index=index, athlete_id=uuid4(), exceeds_role_quota=index in flagged)
        for index in range(len(roles))
    ]
    slots += [
        SimpleNamespace(slot_index=len(roles) + index, athlete_id=None, exceeds_role_quota=False)
        for index in range(empty_slots)
    ]
    effective: dict[UUID, EffectiveAthleteRole] = {
        slot.athlete_id: EffectiveAthleteRole(role=role, club_id=None)
        for slot, role in zip(slots, roles, strict=False)
        if role is not None
    }
    validated_at = datetime.now(UTC) if status == RosterCompositionStatus.VALIDATED else None
    team = SimpleNamespace(composition_status=status, validated_at=validated_at, slots=slots)
    report = evaluate_roster_composition(
        limits=LIMITS,
        roles=[role for role in roles if role is not None],
        competition_ids={uuid4(), uuid4(), uuid4()},
        require_complete=False,
        unresolved_role_count=sum(1 for role in roles if role is None),
    )
    return team, report, effective


def test_validated_roster_in_quota_needs_nothing() -> None:
    team, report, roles = _team(list(ROLES), status=RosterCompositionStatus.VALIDATED)
    assert report.status == RosterCompositionStatus.VALIDATED
    assert not composition_needs_refresh(team, report, effective_roles=roles)  # type: ignore[arg-type]


def test_stored_validated_but_over_quota_needs_refresh() -> None:
    # Un C diventato A: 2 attaccanti su 1, salvato "validated" e nessuno segnato (qa-04).
    roles = [FantasyRole.P, FantasyRole.D, FantasyRole.A, FantasyRole.A]
    team, report, effective = _team(roles, status=RosterCompositionStatus.VALIDATED)
    assert report.status == RosterCompositionStatus.INVALID
    assert composition_needs_refresh(team, report, effective_roles=effective)  # type: ignore[arg-type]


def test_invalid_roster_with_the_excess_already_flagged_is_up_to_date() -> None:
    roles = [FantasyRole.P, FantasyRole.D, FantasyRole.A, FantasyRole.A]
    team, report, effective = _team(roles, status=RosterCompositionStatus.INVALID, flagged={3})
    assert not composition_needs_refresh(team, report, effective_roles=effective)  # type: ignore[arg-type]


def test_invalid_roster_with_the_excess_not_flagged_needs_refresh() -> None:
    roles = [FantasyRole.P, FantasyRole.D, FantasyRole.A, FantasyRole.A]
    team, report, effective = _team(roles, status=RosterCompositionStatus.INVALID)
    assert composition_needs_refresh(team, report, effective_roles=effective)  # type: ignore[arg-type]


def test_flag_no_longer_justified_needs_refresh() -> None:
    # Quote esatte ma un calciatore ancora segnato: `reconcile_roster_overflow` lo toglierebbe.
    team, report, effective = _team(
        list(ROLES), status=RosterCompositionStatus.VALIDATED, flagged={3}
    )
    assert composition_needs_refresh(team, report, effective_roles=effective)  # type: ignore[arg-type]


def test_flag_of_an_unbalanced_trade_stays() -> None:
    # Scambio 2 per 1: 5 calciatori su 4, il secondo C (in più) già segnato.
    roles = [FantasyRole.P, FantasyRole.D, FantasyRole.C, FantasyRole.A, FantasyRole.C]
    team, report, effective = _team(roles, status=RosterCompositionStatus.INVALID, flagged={4})
    assert not composition_needs_refresh(team, report, effective_roles=effective)  # type: ignore[arg-type]


def test_stored_status_different_from_the_evaluation_needs_refresh() -> None:
    # Rosa a 3/4 salvata "invalid" (vecchia regola a rosa completa): la lettura dice "incompleta".
    roles = [FantasyRole.P, FantasyRole.D, FantasyRole.C]
    team, report, effective = _team(roles, status=RosterCompositionStatus.INVALID, empty_slots=1)
    assert report.status == RosterCompositionStatus.INCOMPLETE
    assert composition_needs_refresh(team, report, effective_roles=effective)  # type: ignore[arg-type]
