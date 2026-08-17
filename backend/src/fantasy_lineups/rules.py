"""Approved modules, substitutions, copy/draft and tactical moves."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from database.enums import FantasyModule, FantasyRole, FantasyTurnStatus, LineupSlotKind
from fantasy_turns.rules import (
    INACTIVE_FIXTURE_STATUSES,
    STARTED_FIXTURE_STATUSES,
    ensure_utc,
)

APPROVED_MODULES: tuple[FantasyModule, ...] = tuple(FantasyModule)

MODULE_OUTFIELD: dict[FantasyModule, tuple[int, int, int]] = {
    FantasyModule.M343: (3, 4, 3),
    FantasyModule.M352: (3, 5, 2),
    FantasyModule.M433: (4, 3, 3),
    FantasyModule.M442: (4, 4, 2),
    FantasyModule.M451: (4, 5, 1),
    FantasyModule.M532: (5, 3, 2),
    FantasyModule.M541: (5, 4, 1),
}

STARTER_COUNT = 11
GOALKEEPER_STARTERS = 1
MAX_AUTOMATIC_SUBSTITUTIONS = 5
MAX_TACTICAL_MOVES = 3
BENCH_ORDER_LOCKED_MESSAGE = (
    "Non puoi cambiare l'ordine di panchina di un calciatore la cui partita è già iniziata."
)
TACTICAL_MOVES_EXHAUSTED_MESSAGE = (
    "Hai già usato le 3 mosse tattiche di questo turno. "
    "Non puoi più modificare i calciatori ancora sbloccati."
)
COPIED_NOT_IN_ROSTER_MESSAGE = (
    "Uno o più calciatori della formazione precedente non sono più in rosa e sono stati esclusi."
)
COPIED_UNAVAILABLE_MESSAGE = (
    "Uno o più calciatori non sono disponibili: la loro partita è già iniziata."
)


@dataclass(frozen=True)
class ModuleCounts:
    code: FantasyModule
    goalkeepers: int
    defenders: int
    midfielders: int
    forwards: int

    def for_role(self, role: FantasyRole) -> int:
        if role == FantasyRole.P:
            return self.goalkeepers
        if role == FantasyRole.D:
            return self.defenders
        if role == FantasyRole.C:
            return self.midfielders
        return self.forwards


@dataclass(frozen=True)
class LineupIssue:
    code: str
    message: str


@dataclass(frozen=True)
class LineupPlayerRef:
    athlete_id: object
    role: FantasyRole | None


@dataclass(frozen=True)
class LineupEvaluation:
    valid: bool
    issues: tuple[LineupIssue, ...]
    starter_counts: dict[str, int]


@dataclass(frozen=True)
class AutomaticSubstitution:
    out_athlete_id: object
    in_athlete_id: object
    role: FantasyRole
    order: int


@dataclass(frozen=True)
class SubstitutionResolution:
    substitutions: tuple[AutomaticSubstitution, ...]
    effective_starter_ids: tuple[object, ...]
    module_valid: bool


@dataclass(frozen=True)
class TacticalMoveEvaluation:
    would_consume: bool
    remaining_after: int
    issues: tuple[LineupIssue, ...]


@dataclass(frozen=True)
class CopyLineupResult:
    module: str
    starter_ids: tuple[object, ...]
    bench_ids: tuple[object, ...]
    dropped_athlete_ids: tuple[object, ...]
    unavailable_athlete_ids: tuple[object, ...]
    issues: tuple[LineupIssue, ...]
    blocked: bool
    can_confirm: bool


def parse_module(value: str) -> FantasyModule | None:
    try:
        return FantasyModule(value)
    except ValueError:
        return None


def module_counts(code: FantasyModule) -> ModuleCounts:
    defenders, midfielders, forwards = MODULE_OUTFIELD[code]
    return ModuleCounts(
        code=code,
        goalkeepers=GOALKEEPER_STARTERS,
        defenders=defenders,
        midfielders=midfielders,
        forwards=forwards,
    )


def approved_module_catalog() -> list[ModuleCounts]:
    return [module_counts(code) for code in APPROVED_MODULES]


def starter_template(code: FantasyModule) -> list[FantasyRole]:
    counts = module_counts(code)
    return (
        [FantasyRole.P] * counts.goalkeepers
        + [FantasyRole.D] * counts.defenders
        + [FantasyRole.C] * counts.midfielders
        + [FantasyRole.A] * counts.forwards
    )


def count_roles(players: Sequence[LineupPlayerRef]) -> dict[FantasyRole, int]:
    counter: Counter[FantasyRole] = Counter()
    for player in players:
        if player.role is not None:
            counter[player.role] += 1
    return {role: int(counter.get(role, 0)) for role in FantasyRole}


def evaluate_lineup(
    *,
    module: str,
    starters: Sequence[LineupPlayerRef],
    bench: Sequence[LineupPlayerRef],
    roster_athlete_ids: Sequence[object],
    strict: bool = True,
) -> LineupEvaluation:
    """Validate 7 modules, 1 GK, 11 starters, P–D–C–A counts and roster membership.

    Drafts may pass ``strict=False`` to allow incomplete XI/panchina (EP06-06).
    """
    issues: list[LineupIssue] = []
    parsed = parse_module(module)
    starter_role_counts = count_roles(starters)

    if parsed is None:
        issues.append(
            LineupIssue(
                code="invalid_module",
                message="Modulo non ammesso. Scegli uno dei sette moduli validi.",
            )
        )

    starter_ids = [player.athlete_id for player in starters]
    bench_ids = [player.athlete_id for player in bench]
    all_ids = [*starter_ids, *bench_ids]
    seen: set[object] = set()
    missing_slot = False
    duplicate = False
    for athlete_id in all_ids:
        if athlete_id is None or athlete_id == "":
            missing_slot = True
            continue
        if athlete_id in seen:
            duplicate = True
        seen.add(athlete_id)
    if missing_slot and strict:
        issues.append(
            LineupIssue(
                code="missing_athlete",
                message="Ogni slot della formazione deve contenere un calciatore.",
            )
        )
    if duplicate:
        issues.append(
            LineupIssue(
                code="duplicate_athlete",
                message="Lo stesso calciatore non può comparire più di una volta in formazione.",
            )
        )

    roster_set = {item for item in roster_athlete_ids if item not in {None, ""}}
    if any(athlete_id not in {None, ""} and athlete_id not in roster_set for athlete_id in all_ids):
        issues.append(
            LineupIssue(
                code="athlete_not_in_roster",
                message="Uno o più calciatori schierati non appartengono alla rosa.",
            )
        )

    filled_starters = (
        starters
        if strict
        else [player for player in starters if player.athlete_id not in {None, ""}]
    )
    filled_bench = (
        bench if strict else [player for player in bench if player.athlete_id not in {None, ""}]
    )
    if any(player.role is None for player in filled_starters) or any(
        player.role is None for player in filled_bench
    ):
        issues.append(
            LineupIssue(
                code="unresolved_role",
                message="Uno o più calciatori non hanno un ruolo listone risolvibile (P–D–C–A).",
            )
        )

    if strict and len(starters) != STARTER_COUNT:
        issues.append(
            LineupIssue(
                code="starter_count_invalid",
                message=(
                    f"La formazione deve avere esattamente {STARTER_COUNT} titolari "
                    f"(attuali: {len(starters)})."
                ),
            )
        )

    if strict and starter_role_counts[FantasyRole.P] != GOALKEEPER_STARTERS:
        issues.append(
            LineupIssue(
                code="goalkeeper_count_invalid",
                message=(
                    f"Serve esattamente {GOALKEEPER_STARTERS} portiere titolare "
                    f"(attuali: {starter_role_counts[FantasyRole.P]})."
                ),
            )
        )

    if strict and parsed is not None:
        expected = module_counts(parsed)
        if (
            starter_role_counts[FantasyRole.D] != expected.defenders
            or starter_role_counts[FantasyRole.C] != expected.midfielders
            or starter_role_counts[FantasyRole.A] != expected.forwards
        ):
            issues.append(
                LineupIssue(
                    code="module_role_mismatch",
                    message=(
                        f"Il modulo {parsed.value} richiede "
                        f"{expected.defenders}D–{expected.midfielders}C–{expected.forwards}A "
                        "titolari "
                        f"(attuali: {starter_role_counts[FantasyRole.D]}D–"
                        f"{starter_role_counts[FantasyRole.C]}C–"
                        f"{starter_role_counts[FantasyRole.A]}A)."
                    ),
                )
            )

    unused = [item for item in roster_athlete_ids if item not in {None, ""} and item not in seen]
    if unused and strict:
        issues.append(
            LineupIssue(
                code="bench_incomplete",
                message=(
                    "Tutti i calciatori in rosa devono essere schierati: "
                    f"mancano {len(unused)} in panchina."
                ),
            )
        )

    unique: list[LineupIssue] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in issues:
        key = (item.code, item.message)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(item)

    return LineupEvaluation(
        valid=not unique,
        issues=tuple(unique),
        starter_counts={role.value: starter_role_counts[role] for role in FantasyRole},
    )


def is_athlete_kickoff_locked(
    *,
    now: datetime,
    kickoff_at: datetime | None,
    status_short: str | None = None,
    lock_latched: bool = False,
) -> bool:
    """True when the athlete's real match has started (server clock is authoritative).

    ``lock_latched`` keeps the player frozen after a postponement or kickoff
    change that arrives only after the previously published time elapsed.
    """
    if lock_latched:
        return True
    status = (status_short or "").strip().upper()
    if status in STARTED_FIXTURE_STATUSES:
        return True
    if status in INACTIVE_FIXTURE_STATUSES:
        return False
    if kickoff_at is None:
        return False
    return ensure_utc(now) >= ensure_utc(kickoff_at)


def evaluate_progressive_lock(
    *,
    previous_slots: Mapping[object, str],
    proposed_slots: Mapping[object, str],
    locked_athlete_ids: Iterable[object],
) -> tuple[LineupIssue, ...]:
    """Reject slot changes for athletes whose kickoff has already started."""
    issues: list[LineupIssue] = []
    for athlete_id in locked_athlete_ids:
        previous = previous_slots.get(athlete_id)
        proposed = proposed_slots.get(athlete_id)
        if previous is None:
            if proposed == LineupSlotKind.STARTER.value:
                issues.append(
                    LineupIssue(
                        code="athlete_kickoff_locked",
                        message=(
                            "Uno o più calciatori non sono più modificabili: "
                            "la loro partita è già iniziata."
                        ),
                    )
                )
            continue
        if proposed != previous:
            issues.append(
                LineupIssue(
                    code="athlete_kickoff_locked",
                    message=(
                        "Uno o più calciatori non sono più modificabili: "
                        "la loro partita è già iniziata."
                    ),
                )
            )
    unique: list[LineupIssue] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in issues:
        key = (item.code, item.message)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(item)
    return tuple(unique)


def assert_progressive_lock(
    *,
    previous_slots: Mapping[object, str],
    proposed_slots: Mapping[object, str],
    locked_athlete_ids: Iterable[object],
) -> None:
    from auth.exceptions import ValidationAuthError

    issues = evaluate_progressive_lock(
        previous_slots=previous_slots,
        proposed_slots=proposed_slots,
        locked_athlete_ids=locked_athlete_ids,
    )
    if not issues:
        return
    first = issues[0]
    raise ValidationAuthError(first.message, code=first.code)


def is_lineup_modification_allowed(*, stored: FantasyTurnStatus) -> bool:
    """Turn-level gate: progressive edits stay open on open/locked turns (EP06-03)."""
    return stored in {FantasyTurnStatus.OPEN, FantasyTurnStatus.LOCKED}


def assert_lineup_modification_allowed(*, stored: FantasyTurnStatus) -> None:
    from auth.exceptions import ValidationAuthError

    if stored == FantasyTurnStatus.SCHEDULED:
        raise ValidationAuthError(
            "Il turno non è ancora aperto: la formazione si schiera dopo l'apertura.",
            code="turn_not_open",
        )
    if stored == FantasyTurnStatus.SKIPPED:
        raise ValidationAuthError(
            "Il turno non è stato disputato e la formazione non può essere modificata.",
            code="turn_skipped",
        )
    if is_lineup_modification_allowed(stored=stored):
        return
    raise ValidationAuthError(
        "Modifica fuori tempo: il turno non accetta più cambiamenti di formazione.",
        code="turn_modification_closed",
    )


def remaining_roster_for_bench(
    roster_athlete_ids: Sequence[object],
    starter_athlete_ids: Sequence[object],
) -> list[object]:
    used = {item for item in starter_athlete_ids if item not in {None, ""}}
    return [item for item in roster_athlete_ids if item not in {None, ""} and item not in used]


def ordered_bench_from_roster(
    roster_athlete_ids: Sequence[object],
    starter_athlete_ids: Sequence[object],
    previous_bench_order: Sequence[object] | None = None,
) -> list[object]:
    remaining = remaining_roster_for_bench(roster_athlete_ids, starter_athlete_ids)
    remaining_set = set(remaining)
    ordered: list[object] = []
    for athlete_id in previous_bench_order or ():
        if athlete_id in remaining_set:
            ordered.append(athlete_id)
            remaining_set.discard(athlete_id)
    for athlete_id in remaining:
        if athlete_id in remaining_set:
            ordered.append(athlete_id)
    return ordered


def _dedupe_issues(issues: Sequence[LineupIssue]) -> tuple[LineupIssue, ...]:
    unique: list[LineupIssue] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in issues:
        key = (item.code, item.message)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique.append(item)
    return tuple(unique)


def evaluate_bench_order_lock(
    *,
    previous_bench: Sequence[object],
    proposed_bench: Sequence[object],
    locked_athlete_ids: Iterable[object],
) -> tuple[LineupIssue, ...]:
    """Reject bench-order changes that cross a locked player (no retroactive advantage)."""
    locked = {item for item in locked_athlete_ids if item not in {None, ""}}
    previous = [item for item in previous_bench if item not in {None, ""}]
    proposed = [item for item in proposed_bench if item not in {None, ""}]
    if not locked or not previous:
        return ()

    previous_set = set(previous)
    proposed_set = set(proposed)
    common = [item for item in previous if item in proposed_set]
    locked_remaining = [item for item in previous if item in locked and item in proposed_set]
    issues: list[LineupIssue] = []

    for locked_id in locked_remaining:
        previous_index = previous.index(locked_id)
        proposed_index = proposed.index(locked_id)
        crossed = False
        for other in common:
            if other == locked_id:
                continue
            was_before = previous.index(other) < previous_index
            now_before = proposed.index(other) < proposed_index
            if was_before != now_before:
                crossed = True
                break
        if crossed:
            issues.append(
                LineupIssue(code="bench_order_locked", message=BENCH_ORDER_LOCKED_MESSAGE)
            )
            break

    if locked_remaining and not issues:
        last_locked_proposed = max(proposed.index(item) for item in locked_remaining)
        for athlete_id in proposed:
            if athlete_id not in previous_set and proposed.index(athlete_id) < last_locked_proposed:
                issues.append(
                    LineupIssue(code="bench_order_locked", message=BENCH_ORDER_LOCKED_MESSAGE)
                )
                break

    return _dedupe_issues(issues)


def assert_bench_order_lock(
    *,
    previous_bench: Sequence[object],
    proposed_bench: Sequence[object],
    locked_athlete_ids: Iterable[object],
) -> None:
    from auth.exceptions import ValidationAuthError

    issues = evaluate_bench_order_lock(
        previous_bench=previous_bench,
        proposed_bench=proposed_bench,
        locked_athlete_ids=locked_athlete_ids,
    )
    if not issues:
        return
    first = issues[0]
    raise ValidationAuthError(first.message, code=first.code)


def resolve_automatic_substitutions(
    *,
    module: str,
    starters: Sequence[LineupPlayerRef],
    bench: Sequence[LineupPlayerRef],
    played_athlete_ids: Sequence[object],
) -> SubstitutionResolution:
    """Apply up to 5 same-role substitutions walking the ordered bench."""
    played = {item for item in played_athlete_ids if item not in {None, ""}}
    substitutions: list[AutomaticSubstitution] = []
    replaced: set[object] = set()
    effective = [player.athlete_id for player in starters]
    role_by_id: dict[object, FantasyRole | None] = {}
    for player in [*starters, *bench]:
        if player.athlete_id not in {None, ""}:
            role_by_id[player.athlete_id] = player.role

    for bench_player in bench:
        if len(substitutions) >= MAX_AUTOMATIC_SUBSTITUTIONS:
            break
        if bench_player.athlete_id in {None, ""} or bench_player.athlete_id not in played:
            continue
        if bench_player.role is None:
            continue
        starter_index = next(
            (
                index
                for index, starter in enumerate(starters)
                if starter.athlete_id not in {None, ""}
                and starter.athlete_id not in replaced
                and starter.role == bench_player.role
                and starter.athlete_id not in played
            ),
            None,
        )
        if starter_index is None:
            continue
        outgoing = starters[starter_index]
        replaced.add(outgoing.athlete_id)
        effective[starter_index] = bench_player.athlete_id
        substitutions.append(
            AutomaticSubstitution(
                out_athlete_id=outgoing.athlete_id,
                in_athlete_id=bench_player.athlete_id,
                role=bench_player.role,
                order=len(substitutions) + 1,
            )
        )

    parsed = parse_module(module)
    module_valid = False
    if parsed is not None:
        expected = module_counts(parsed)
        counts = count_roles(
            [
                LineupPlayerRef(athlete_id=athlete_id, role=role_by_id.get(athlete_id))
                for athlete_id in effective
            ]
        )
        module_valid = (
            counts[FantasyRole.P] == expected.goalkeepers
            and counts[FantasyRole.D] == expected.defenders
            and counts[FantasyRole.C] == expected.midfielders
            and counts[FantasyRole.A] == expected.forwards
        )

    return SubstitutionResolution(
        substitutions=tuple(substitutions),
        effective_starter_ids=tuple(effective),
        module_valid=module_valid,
    )


def lineup_signature(
    *,
    module: str,
    starter_ids: Sequence[object],
    bench_ids: Sequence[object],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Stable fingerprint of a saved formation (module + ordered slots)."""
    return (
        str(module),
        tuple(str(item) for item in starter_ids if item not in {None, ""}),
        tuple(str(item) for item in bench_ids if item not in {None, ""}),
    )


def is_tactical_window_active(*, any_athlete_locked: bool) -> bool:
    """Moves start after at least one real kickoff has locked a roster player."""
    return bool(any_athlete_locked)


def remaining_tactical_moves(*, used: int, maximum: int = MAX_TACTICAL_MOVES) -> int:
    return max(0, maximum - max(0, used))


def evaluate_tactical_move(
    *,
    has_saved_lineup: bool,
    any_athlete_locked: bool,
    moves_used: int,
    proposed_module: str,
    proposed_starter_ids: Sequence[object],
    proposed_bench_ids: Sequence[object],
    previous_module: str | None = None,
    previous_starter_ids: Sequence[object] | None = None,
    previous_bench_ids: Sequence[object] | None = None,
    maximum: int = MAX_TACTICAL_MOVES,
) -> TacticalMoveEvaluation:
    """One confirmed save in the progressive window consumes one of three moves.

    The initial formation (FR-FOR-01) and identical re-saves do not consume.
    Automatic substitutions are out of this engine and never consume a move.
    A composed save (module + unlocked swaps + bench order) counts as one move.
    """
    changed = False
    if has_saved_lineup:
        changed = lineup_signature(
            module=proposed_module,
            starter_ids=proposed_starter_ids,
            bench_ids=proposed_bench_ids,
        ) != lineup_signature(
            module=previous_module or "",
            starter_ids=previous_starter_ids or (),
            bench_ids=previous_bench_ids or (),
        )
    would_consume = bool(
        has_saved_lineup
        and is_tactical_window_active(any_athlete_locked=any_athlete_locked)
        and changed
    )
    issues: list[LineupIssue] = []
    if would_consume and moves_used >= maximum:
        issues.append(
            LineupIssue(
                code="tactical_moves_exhausted",
                message=TACTICAL_MOVES_EXHAUSTED_MESSAGE,
            )
        )
    remaining_after = remaining_tactical_moves(
        used=moves_used + (1 if would_consume else 0),
        maximum=maximum,
    )
    return TacticalMoveEvaluation(
        would_consume=would_consume,
        remaining_after=remaining_after,
        issues=_dedupe_issues(issues),
    )


def assert_tactical_move(
    *,
    has_saved_lineup: bool,
    any_athlete_locked: bool,
    moves_used: int,
    proposed_module: str,
    proposed_starter_ids: Sequence[object],
    proposed_bench_ids: Sequence[object],
    previous_module: str | None = None,
    previous_starter_ids: Sequence[object] | None = None,
    previous_bench_ids: Sequence[object] | None = None,
    maximum: int = MAX_TACTICAL_MOVES,
) -> TacticalMoveEvaluation:
    from auth.exceptions import ValidationAuthError

    evaluation = evaluate_tactical_move(
        has_saved_lineup=has_saved_lineup,
        any_athlete_locked=any_athlete_locked,
        moves_used=moves_used,
        proposed_module=proposed_module,
        proposed_starter_ids=proposed_starter_ids,
        proposed_bench_ids=proposed_bench_ids,
        previous_module=previous_module,
        previous_starter_ids=previous_starter_ids,
        previous_bench_ids=previous_bench_ids,
        maximum=maximum,
    )
    if not evaluation.issues:
        return evaluation
    first = evaluation.issues[0]
    raise ValidationAuthError(first.message, code=first.code)


def copy_previous_lineup(
    *,
    previous_module: str,
    previous_starter_ids: Sequence[object],
    previous_bench_ids: Sequence[object],
    roster_athlete_ids: Sequence[object],
    locked_athlete_ids: Iterable[object] | None = None,
    current_confirmed_slots: Mapping[object, str] | None = None,
    current_confirmed_bench: Sequence[object] | None = None,
    role_by_athlete_id: Mapping[object, FantasyRole | None] | None = None,
) -> CopyLineupResult:
    """Revalidate a previous lineup against current roster and kickoff availability."""
    roster_set = {item for item in roster_athlete_ids if item not in {None, ""}}
    locked = {item for item in (locked_athlete_ids or ()) if item not in {None, ""}}
    confirmed = dict(current_confirmed_slots or {})
    dropped: list[object] = []
    unavailable: list[object] = []
    starters: list[object] = []

    for athlete_id in previous_starter_ids:
        if athlete_id in {None, ""}:
            starters.append("")
            continue
        if athlete_id not in roster_set:
            dropped.append(athlete_id)
            starters.append("")
            continue
        if athlete_id in locked and confirmed.get(athlete_id) != LineupSlotKind.STARTER.value:
            unavailable.append(athlete_id)
            starters.append("")
            continue
        starters.append(athlete_id)
    while len(starters) < STARTER_COUNT:
        starters.append("")
    starter_ids = starters[:STARTER_COUNT]
    starter_set = {item for item in starter_ids if item not in {None, ""}}

    for athlete_id in previous_bench_ids:
        if (
            athlete_id not in {None, ""}
            and athlete_id not in roster_set
            and athlete_id not in dropped
        ):
            dropped.append(athlete_id)

    previous_bench_kept = [
        item
        for item in previous_bench_ids
        if item not in {None, ""} and item in roster_set and item not in starter_set
    ]
    displaced = [item for item in unavailable if item in roster_set and item not in starter_set]
    bench_ids = ordered_bench_from_roster(
        roster_athlete_ids,
        starter_ids,
        [*previous_bench_kept, *displaced],
    )

    lock_issues = [
        *evaluate_progressive_lock(
            previous_slots=confirmed,
            proposed_slots={
                **{
                    item: LineupSlotKind.STARTER.value
                    for item in starter_ids
                    if item not in {None, ""}
                },
                **{
                    item: LineupSlotKind.BENCH.value for item in bench_ids if item not in {None, ""}
                },
            },
            locked_athlete_ids=locked,
        ),
        *evaluate_bench_order_lock(
            previous_bench=current_confirmed_bench or (),
            proposed_bench=bench_ids,
            locked_athlete_ids=locked,
        ),
    ]

    issues: list[LineupIssue] = []
    if dropped:
        issues.append(
            LineupIssue(code="copied_athlete_not_in_roster", message=COPIED_NOT_IN_ROSTER_MESSAGE)
        )
    if unavailable:
        issues.append(
            LineupIssue(code="copied_athlete_unavailable", message=COPIED_UNAVAILABLE_MESSAGE)
        )
    issues.extend(lock_issues)

    roles = role_by_athlete_id or {}
    confirmation = evaluate_lineup(
        module=previous_module,
        starters=[
            LineupPlayerRef(
                athlete_id=athlete_id,
                role=roles.get(athlete_id) if athlete_id not in {None, ""} else None,
            )
            for athlete_id in starter_ids
        ],
        bench=[
            LineupPlayerRef(
                athlete_id=athlete_id,
                role=roles.get(athlete_id) if athlete_id not in {None, ""} else None,
            )
            for athlete_id in bench_ids
        ],
        roster_athlete_ids=roster_athlete_ids,
    )
    return CopyLineupResult(
        module=previous_module,
        starter_ids=tuple(starter_ids),
        bench_ids=tuple(bench_ids),
        dropped_athlete_ids=tuple(dropped),
        unavailable_athlete_ids=tuple(unavailable),
        issues=_dedupe_issues(issues),
        blocked=bool(lock_issues),
        can_confirm=confirmation.valid and not lock_issues,
    )


def assert_copy_previous_lineup(result: CopyLineupResult) -> CopyLineupResult:
    from auth.exceptions import ValidationAuthError

    if not result.blocked:
        return result
    first = next(
        (
            item
            for item in result.issues
            if item.code in {"athlete_kickoff_locked", "bench_order_locked"}
        ),
        result.issues[0] if result.issues else None,
    )
    if first is None:
        raise ValidationAuthError(
            "Modifica fuori tempo: il turno non accetta più cambiamenti di formazione.",
            code="turn_modification_closed",
        )
    raise ValidationAuthError(first.message, code=first.code)
