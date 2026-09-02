"""HTTP schemas for european fantasy turns (EP06-01)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from auth.schemas import ApiModel


class FantasyTurnFixtureResponse(ApiModel):
    id: str
    fixture_id: str = Field(alias="fixtureId")
    included_reason: str = Field(alias="includedReason")
    excluded_at: datetime | None = Field(default=None, alias="excludedAt")
    kickoff_at: datetime | None = Field(default=None, alias="kickoffAt")
    observed_kickoff_at: datetime | None = Field(default=None, alias="observedKickoffAt")
    lock_latched_at: datetime | None = Field(default=None, alias="lockLatchedAt")
    status_short: str = Field(alias="statusShort")
    status_elapsed: int | None = Field(default=None, alias="statusElapsed")
    home_goals: int | None = Field(default=None, alias="homeGoals")
    away_goals: int | None = Field(default=None, alias="awayGoals")
    home_club_name: str = Field(alias="homeClubName")
    away_club_name: str = Field(alias="awayClubName")
    home_club_logo_url: str | None = Field(default=None, alias="homeClubLogoUrl")
    away_club_logo_url: str | None = Field(default=None, alias="awayClubLogoUrl")
    competition_name: str | None = Field(default=None, alias="competitionName")
    provider_id: int = Field(alias="providerId")
    # Freschezza del dato normalizzato (EP13-P04): quando è stato aggiornato
    # l'ultima volta e quanto ci si può fidare di ciò che si vede.
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    feed_state: str = Field(default="fresh", alias="feedState")
    feed_state_label: str = Field(default="Aggiornato", alias="feedStateLabel")


class FixtureTimelineEventResponse(ApiModel):
    """Evento della cronologia partita (EP13-P04)."""

    id: str
    minute_elapsed: int | None = Field(default=None, alias="minuteElapsed")
    minute_extra: int | None = Field(default=None, alias="minuteExtra")
    minute_label: str = Field(alias="minuteLabel")
    event_type: str = Field(alias="eventType")
    event_detail: str | None = Field(default=None, alias="eventDetail")
    scoring_kind: str | None = Field(default=None, alias="scoringKind")
    club_id: str | None = Field(default=None, alias="clubId")
    club_name: str | None = Field(default=None, alias="clubName")
    athlete_id: str | None = Field(default=None, alias="athleteId")
    athlete_name: str | None = Field(default=None, alias="athleteName")
    related_athlete_id: str | None = Field(default=None, alias="relatedAthleteId")
    related_athlete_name: str | None = Field(default=None, alias="relatedAthleteName")
    comments: str | None = None


class FixtureLineupPlayerResponse(ApiModel):
    athlete_id: str | None = Field(default=None, alias="athleteId")
    name: str
    shirt_number: int | None = Field(default=None, alias="shirtNumber")
    position: str | None = None
    grid: str | None = None
    photo_url: str | None = Field(default=None, alias="photoUrl")


class FixtureLineupResponse(ApiModel):
    club_name: str = Field(alias="clubName")
    club_logo_url: str | None = Field(default=None, alias="clubLogoUrl")
    formation: str | None = None
    coach_name: str | None = Field(default=None, alias="coachName")
    starters: list[FixtureLineupPlayerResponse] = Field(default_factory=list)
    bench: list[FixtureLineupPlayerResponse] = Field(default_factory=list)


class FixtureLiveDetailResponse(ApiModel):
    """Dettaglio partita: risultato, formazioni ufficiali e cronologia."""

    fixture_id: str = Field(alias="fixtureId")
    turn_id: str = Field(alias="turnId")
    league_id: str = Field(alias="leagueId")
    provider_id: int = Field(alias="providerId")
    competition_name: str | None = Field(default=None, alias="competitionName")
    home_club_id: str = Field(alias="homeClubId")
    away_club_id: str = Field(alias="awayClubId")
    home_club_name: str = Field(alias="homeClubName")
    away_club_name: str = Field(alias="awayClubName")
    home_club_logo_url: str | None = Field(default=None, alias="homeClubLogoUrl")
    away_club_logo_url: str | None = Field(default=None, alias="awayClubLogoUrl")
    home_goals: int | None = Field(default=None, alias="homeGoals")
    away_goals: int | None = Field(default=None, alias="awayGoals")
    status_short: str = Field(alias="statusShort")
    status_elapsed: int | None = Field(default=None, alias="statusElapsed")
    venue_name: str | None = Field(default=None, alias="venueName")
    venue_city: str | None = Field(default=None, alias="venueCity")
    referee: str | None = None
    kickoff_at: datetime | None = Field(default=None, alias="kickoffAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    feed_state: str = Field(alias="feedState")
    feed_state_label: str = Field(alias="feedStateLabel")
    home_lineup: FixtureLineupResponse | None = Field(default=None, alias="homeLineup")
    away_lineup: FixtureLineupResponse | None = Field(default=None, alias="awayLineup")
    events: list[FixtureTimelineEventResponse] = Field(default_factory=list)


class FantasyTurnSummaryResponse(ApiModel):
    id: str
    league_id: str = Field(alias="leagueId")
    number: int
    kind: str
    window_start_at: datetime = Field(alias="windowStartAt")
    window_end_at: datetime = Field(alias="windowEndAt")
    opens_at: datetime | None = Field(default=None, alias="opensAt")
    closes_at: datetime | None = Field(default=None, alias="closesAt")
    cutoff_at: datetime | None = Field(default=None, alias="cutoffAt")
    status: str
    effective_status: str = Field(alias="effectiveStatus")
    skip_reason: str | None = Field(default=None, alias="skipReason")
    fixture_count: int = Field(alias="fixtureCount")
    generated_at: datetime = Field(alias="generatedAt")
    modification_allowed: bool = Field(alias="modificationAllowed")
    # Stato aggregato derivato dalle fixture reali (§23): completed | live |
    # scheduled | needs_update — distinto dal ciclo di vita fantasy
    # (status/effectiveStatus: scheduled/open/locked/skipped).
    match_status: str = Field(alias="matchStatus")


class FantasyTurnDetailResponse(FantasyTurnSummaryResponse):
    homologation_status: Literal["provisional", "homologated"] = Field(alias="homologationStatus")
    fixtures: list[FantasyTurnFixtureResponse] = Field(default_factory=list)


class FantasyTurnPreviewResponse(ApiModel):
    kind: str
    window_start_at: datetime = Field(alias="windowStartAt")
    window_end_at: datetime = Field(alias="windowEndAt")
    timezone: str
    eligible_count: int = Field(alias="eligibleCount")
    min_required: int = Field(alias="minRequired")
    threshold_ok: bool = Field(alias="thresholdOk")
    skip_reason: str | None = Field(default=None, alias="skipReason")
    cutoff_at: datetime | None = Field(default=None, alias="cutoffAt")
    fixtures: list[FantasyTurnFixtureResponse] = Field(default_factory=list)


class GenerateFantasyTurnRequest(ApiModel):
    kind: Literal["weekend", "midweek"]
    anchor_date: date = Field(alias="anchorDate")


class ExcludeFantasyTurnFixtureRequest(ApiModel):
    fixture_id: UUID = Field(alias="fixtureId")


class EnsureFantasyTurnsResponse(ApiModel):
    league_id: str = Field(alias="leagueId")
    created: int
    opened: int
    upgraded: int
    duplicates: int
    waiting: int
    horizon_days: int = Field(alias="horizonDays")


class FantasyCalendarRefreshResultResponse(ApiModel):
    """Esito del comando unico "Aggiorna calendario" (backfill stagionale)."""

    league_id: str = Field(alias="leagueId")
    fixtures_created: int = Field(alias="fixturesCreated")
    fixtures_updated: int = Field(alias="fixturesUpdated")
    fixtures_unchanged: int = Field(alias="fixturesUnchanged")
    fixtures_needing_date: int = Field(alias="fixturesNeedingDate")
    rounds_created: int = Field(alias="roundsCreated")
    rounds_updated: int = Field(alias="roundsUpdated")
    rounds_realigned: int = Field(alias="roundsRealigned")
    # Turni "fantasma" (senza nessuna partita reale) rimossi in questo giro.
    rounds_removed: int = Field(default=0, alias="roundsRemoved")
    message: str


class FantasyCalendarRefreshJobResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    message: str


class FantasyCalendarRefreshProgressResponse(ApiModel):
    job_id: str = Field(alias="jobId")
    status: str
    percent: int
    stage: str
    message: str
    error_code: str | None = Field(default=None, alias="errorCode")
    result: FantasyCalendarRefreshResultResponse | None = None


class PendingFixtureResponse(ApiModel):
    """Fixture nota (competizione/squadre/round) ma senza data/ora dal provider."""

    fixture_id: str = Field(alias="fixtureId")
    competition_name: str | None = Field(default=None, alias="competitionName")
    round_label: str | None = Field(default=None, alias="roundLabel")
    home_club_name: str = Field(alias="homeClubName")
    away_club_name: str = Field(alias="awayClubName")
    status_short: str = Field(alias="statusShort")


class ApplyRoundCorrectionRequest(ApiModel):
    reason: str = Field(min_length=1)


class RoundHomologationResponse(ApiModel):
    round_id: str = Field(alias="roundId")
    homologation_status: Literal["provisional", "homologated"] = Field(alias="homologationStatus")
    homologated_at: datetime | None = Field(default=None, alias="homologatedAt")
    formula_version: str | None = Field(default=None, alias="formulaVersion")


class RoundCalculationResponse(ApiModel):
    """Esito di `calculate_league_round` (EP-turni-calcolo) — stessa forma sia dal
    pulsante per-lega sia (aggregata) dal pulsante massivo dell'operatore."""

    round_id: str = Field(alias="roundId")
    round_number: int = Field(alias="roundNumber")
    fixtures_scored: int = Field(alias="fixturesScored")
    fallback_resolved_from_draft: int = Field(default=0, alias="fallbackResolvedFromDraft")
    fallback_resolved_from_previous_round: int = Field(
        default=0, alias="fallbackResolvedFromPreviousRound"
    )
    fallback_resolved_as_zero: int = Field(default=0, alias="fallbackResolvedAsZero")
    result_final: bool = Field(alias="resultFinal")
    homologated: bool
