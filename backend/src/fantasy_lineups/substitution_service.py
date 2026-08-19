"""Compute and persist round-level effective lineups (EP07-04 / FR-SUB-01).

Resolves, for every fantasy team in a turn, which starters lack a valid
statistical vote (EP07-02) and applies the automatic substitutions described
in ``fantasy_lineups.rules.resolve_automatic_substitutions``. The result is
persisted idempotently: a recompute (e.g. after a rating correction, EP07-07)
overwrites the existing row for ``(round_id, fantasy_team_id)`` instead of
duplicating it, so it stays deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth.exceptions import ValidationAuthError
from database.enums import LineupSlotKind
from fantasy_lineups.models import EffectiveLineup, LineupSubmission
from fantasy_lineups.rules import (
    LineupPlayerRef,
    SubstitutionResolution,
    resolve_automatic_substitutions,
)
from fantasy_lineups.validators import validate_max_automatic_substitutions_override
from fantasy_ratings.config import default_formula_config
from fantasy_ratings.models import PlayerMatchRating
from fantasy_turns.homologation import assert_round_not_homologated
from fantasy_turns.models import FantasyRound, FantasyRoundFixture
from leagues.models.league_rules import LeagueRules

UpsertResult = str  # created | updated | unchanged


@dataclass
class EffectiveLineupCounters:
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    def incr(self, result: UpsertResult) -> None:
        setattr(self, result, getattr(self, result) + 1)


@dataclass
class RoundEffectiveLineupsResult:
    round_id: UUID
    league_id: UUID
    max_automatic_substitutions: int
    teams: int
    counters: EffectiveLineupCounters = field(default_factory=EffectiveLineupCounters)


def compute_round_effective_lineups(
    session: Session,
    *,
    round_id: UUID,
    formula_version: str | None = None,
    max_automatic_substitutions: int | None = None,
) -> RoundEffectiveLineupsResult:
    fantasy_round = session.get(FantasyRound, round_id)
    if fantasy_round is None:
        raise ValidationAuthError("Turno non trovato.", code="turn_not_found")
    assert_round_not_homologated(fantasy_round)

    rules = session.execute(
        select(LeagueRules).where(LeagueRules.league_id == fantasy_round.league_id)
    ).scalar_one_or_none()
    if rules is None:
        raise ValidationAuthError("Regolamento di lega non trovato.", code="league_rules_not_found")

    resolved_limit = (
        validate_max_automatic_substitutions_override(max_automatic_substitutions)
        if max_automatic_substitutions is not None
        else rules.max_automatic_substitutions
    )

    fixture_ids = list(
        session.scalars(
            select(FantasyRoundFixture.fixture_id).where(
                FantasyRoundFixture.round_id == round_id,
                FantasyRoundFixture.excluded_at.is_(None),
            )
        ).all()
    )

    version = formula_version or default_formula_config().version
    eligible_ids: set[UUID] = set()
    if fixture_ids:
        eligible_ids = set(
            session.scalars(
                select(PlayerMatchRating.athlete_id).where(
                    PlayerMatchRating.fixture_id.in_(fixture_ids),
                    PlayerMatchRating.formula_version == version,
                    PlayerMatchRating.eligible.is_(True),
                    PlayerMatchRating.athlete_id.is_not(None),
                )
            ).all()
        )

    submissions = session.scalars(
        select(LineupSubmission)
        .where(LineupSubmission.round_id == round_id)
        .options(selectinload(LineupSubmission.players))
    ).all()

    counters = EffectiveLineupCounters()
    for submission in submissions:
        starters = [
            LineupPlayerRef(athlete_id=player.athlete_id, role=player.role)
            for player in submission.players
            if player.slot_kind == LineupSlotKind.STARTER
        ]
        bench = [
            LineupPlayerRef(athlete_id=player.athlete_id, role=player.role)
            for player in submission.players
            if player.slot_kind == LineupSlotKind.BENCH
        ]
        resolved = resolve_automatic_substitutions(
            module=submission.module.value,
            starters=starters,
            bench=bench,
            played_athlete_ids=list(eligible_ids),
            max_substitutions=resolved_limit,
        )
        _upsert_effective_lineup(
            session,
            league_id=fantasy_round.league_id,
            round_id=round_id,
            submission=submission,
            resolved=resolved,
            max_automatic_substitutions=resolved_limit,
            counters=counters,
        )

    session.flush()
    return RoundEffectiveLineupsResult(
        round_id=round_id,
        league_id=fantasy_round.league_id,
        max_automatic_substitutions=resolved_limit,
        teams=len(submissions),
        counters=counters,
    )


def get_effective_lineup(
    session: Session,
    *,
    round_id: UUID,
    fantasy_team_id: UUID,
) -> EffectiveLineup | None:
    return session.execute(
        select(EffectiveLineup).where(
            EffectiveLineup.round_id == round_id,
            EffectiveLineup.fantasy_team_id == fantasy_team_id,
        )
    ).scalar_one_or_none()


def _substitution_payload(resolved: SubstitutionResolution) -> list[dict[str, Any]]:
    return [
        {
            "outAthleteId": str(item.out_athlete_id),
            "inAthleteId": str(item.in_athlete_id),
            "role": item.role.value,
            "order": item.order,
        }
        for item in resolved.substitutions
    ]


def _skipped_payload(resolved: SubstitutionResolution) -> list[dict[str, Any]]:
    return [
        {
            "athleteId": str(item.athlete_id),
            "role": item.role.value if item.role is not None else None,
            "reason": item.reason,
        }
        for item in resolved.skipped
    ]


def _upsert_effective_lineup(
    session: Session,
    *,
    league_id: UUID,
    round_id: UUID,
    submission: LineupSubmission,
    resolved: SubstitutionResolution,
    max_automatic_substitutions: int,
    counters: EffectiveLineupCounters,
) -> EffectiveLineup:
    effective_starter_ids = [str(item) for item in resolved.effective_starter_ids]
    substitutions_json = _substitution_payload(resolved)
    skipped_json = _skipped_payload(resolved)

    row = session.execute(
        select(EffectiveLineup).where(
            EffectiveLineup.round_id == round_id,
            EffectiveLineup.fantasy_team_id == submission.fantasy_team_id,
        )
    ).scalar_one_or_none()

    if row is None:
        row = EffectiveLineup(
            league_id=league_id,
            round_id=round_id,
            fantasy_team_id=submission.fantasy_team_id,
            submission_id=submission.id,
            module=submission.module,
            module_valid=resolved.module_valid,
            max_automatic_substitutions=max_automatic_substitutions,
            effective_starter_ids=effective_starter_ids,
            substitutions_json=substitutions_json,
            skipped_json=skipped_json,
            computed_at=datetime.now(UTC),
        )
        session.add(row)
        counters.incr("created")
        return row

    unchanged = (
        row.submission_id == submission.id
        and row.module == submission.module
        and row.module_valid == resolved.module_valid
        and row.max_automatic_substitutions == max_automatic_substitutions
        and row.effective_starter_ids == effective_starter_ids
        and row.substitutions_json == substitutions_json
        and row.skipped_json == skipped_json
    )
    if unchanged:
        counters.incr("unchanged")
        return row

    row.submission_id = submission.id
    row.module = submission.module
    row.module_valid = resolved.module_valid
    row.max_automatic_substitutions = max_automatic_substitutions
    row.effective_starter_ids = effective_starter_ids
    row.substitutions_json = substitutions_json
    row.skipped_json = skipped_json
    row.computed_at = datetime.now(UTC)
    counters.incr("updated")
    return row
