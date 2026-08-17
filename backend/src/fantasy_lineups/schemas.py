"""HTTP schemas for fantasy lineups (EP06-02 / EP06-03 / EP06-04 / EP06-05 / EP06-06)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from auth.schemas import ApiModel

FantasyModuleLiteral = Literal[
    "3-4-3",
    "3-5-2",
    "4-3-3",
    "4-4-2",
    "4-5-1",
    "5-3-2",
    "5-4-1",
]


class LineupIssueResponse(ApiModel):
    code: str
    message: str


class ModuleCountsResponse(ApiModel):
    code: str
    goalkeepers: int
    defenders: int
    midfielders: int
    forwards: int


class LineupRosterPlayerResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str = Field(alias="athleteName")
    role: str | None = None
    slot_index: int = Field(alias="slotIndex")
    locked: bool = False
    lock_latched: bool = Field(default=False, alias="lockLatched")
    kickoff_at: datetime | None = Field(default=None, alias="kickoffAt")
    fixture_status: str | None = Field(default=None, alias="fixtureStatus")


class LineupPlayerResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str = Field(alias="athleteName")
    role: str
    slot_kind: str = Field(alias="slotKind")
    sort_order: int = Field(alias="sortOrder")


class SavedLineupResponse(ApiModel):
    id: str
    module: str
    revision: int
    submitted_at: datetime = Field(alias="submittedAt")
    starters: list[LineupPlayerResponse] = Field(default_factory=list)
    bench: list[LineupPlayerResponse] = Field(default_factory=list)


class PreviousLineupResponse(ApiModel):
    round_id: str = Field(alias="roundId")
    round_number: int = Field(alias="roundNumber")
    module: str
    starters: list[LineupPlayerResponse] = Field(default_factory=list)
    bench: list[LineupPlayerResponse] = Field(default_factory=list)


class LineupDraftResponse(ApiModel):
    module: str
    starter_athlete_ids: list[str] = Field(alias="starterAthleteIds")
    bench_athlete_ids: list[str] = Field(alias="benchAthleteIds")
    saved_at: datetime = Field(alias="savedAt")
    copy_source_round_id: str | None = Field(default=None, alias="copySourceRoundId")
    copy_source_round_number: int | None = Field(default=None, alias="copySourceRoundNumber")


class TacticalMoveResponse(ApiModel):
    sequence: int
    status: str
    used_at: datetime = Field(alias="usedAt")
    from_module: str = Field(alias="fromModule")
    to_module: str = Field(alias="toModule")


class LineupContextResponse(ApiModel):
    league_id: str = Field(alias="leagueId")
    round_id: str = Field(alias="roundId")
    round_number: int = Field(alias="roundNumber")
    kind: str
    cutoff_at: datetime | None = Field(default=None, alias="cutoffAt")
    status: str
    effective_status: str = Field(alias="effectiveStatus")
    modification_allowed: bool = Field(alias="modificationAllowed")
    server_now: datetime = Field(alias="serverNow")
    max_automatic_substitutions: int = Field(alias="maxAutomaticSubstitutions")
    max_tactical_moves: int = Field(alias="maxTacticalMoves")
    tactical_moves_used: int = Field(alias="tacticalMovesUsed")
    tactical_moves_remaining: int = Field(alias="tacticalMovesRemaining")
    tactical_moves: list[TacticalMoveResponse] = Field(
        default_factory=list,
        alias="tacticalMoves",
    )
    modules: list[ModuleCountsResponse] = Field(default_factory=list)
    roster: list[LineupRosterPlayerResponse] = Field(default_factory=list)
    lineup: SavedLineupResponse | None = None
    previous_lineup: PreviousLineupResponse | None = Field(default=None, alias="previousLineup")
    draft: LineupDraftResponse | None = None
    copy_available: bool = Field(default=False, alias="copyAvailable")
    copy_issues: list[LineupIssueResponse] = Field(default_factory=list, alias="copyIssues")
    issues: list[LineupIssueResponse] = Field(default_factory=list)


class SaveLineupRequest(ApiModel):
    module: FantasyModuleLiteral
    starter_athlete_ids: list[UUID] = Field(alias="starterAthleteIds")
    bench_athlete_ids: list[UUID] = Field(alias="benchAthleteIds")


class SaveLineupDraftRequest(ApiModel):
    module: FantasyModuleLiteral
    starter_athlete_ids: list[str] = Field(alias="starterAthleteIds")
    bench_athlete_ids: list[str] = Field(alias="benchAthleteIds")


class ComputeEffectiveLineupsRequest(ApiModel):
    max_automatic_substitutions: int | None = Field(default=None, alias="maxAutomaticSubstitutions")


class ComputeEffectiveLineupsResponse(ApiModel):
    round_id: str = Field(alias="roundId")
    max_automatic_substitutions: int = Field(alias="maxAutomaticSubstitutions")
    teams: int
    created: int
    updated: int
    unchanged: int


class SubstitutionResponse(ApiModel):
    out_athlete_id: str = Field(alias="outAthleteId")
    in_athlete_id: str = Field(alias="inAthleteId")
    role: str
    order: int


class SkippedBenchCandidateResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    role: str | None = None
    reason: str


class EffectiveLineupResponse(ApiModel):
    id: str
    round_id: str = Field(alias="roundId")
    fantasy_team_id: str = Field(alias="fantasyTeamId")
    submission_id: str = Field(alias="submissionId")
    module: str
    module_valid: bool = Field(alias="moduleValid")
    max_automatic_substitutions: int = Field(alias="maxAutomaticSubstitutions")
    effective_starter_ids: list[str] = Field(alias="effectiveStarterIds")
    substitutions: list[SubstitutionResponse] = Field(default_factory=list)
    skipped: list[SkippedBenchCandidateResponse] = Field(default_factory=list)
    computed_at: datetime = Field(alias="computedAt")
