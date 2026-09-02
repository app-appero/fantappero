"""HTTP schemas for AI-assisted advice endpoints (EP10-02..05)."""

from __future__ import annotations

from pydantic import Field

from auth.schemas import ApiModel


class LineupSuggestionResponse(ApiModel):
    starter_athlete_id: str = Field(alias="starterAthleteId")
    starter_name: str = Field(alias="starterName")
    bench_athlete_id: str = Field(alias="benchAthleteId")
    bench_name: str = Field(alias="benchName")
    reason: str


class ViceallenatoreAdviceResponse(ApiModel):
    suggestions: list[LineupSuggestionResponse]
    modification_allowed: bool = Field(alias="modificationAllowed")
    message: str | None = None
    interaction_id: str | None = Field(default=None, alias="interactionId")


class AthleteComparisonRowResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    name: str
    role: str | None = None
    avg_rating: float | None = Field(default=None, alias="avgRating")
    recent_minutes_avg: float | None = Field(default=None, alias="recentMinutesAvg")
    injured: bool | None = None
    is_free_agent_in_league: bool | None = Field(default=None, alias="isFreeAgentInLeague")
    next_opponent_name: str | None = Field(default=None, alias="nextOpponentName")


class OsservatoreResultResponse(ApiModel):
    rows: list[AthleteComparisonRowResponse]
    interaction_id: str = Field(alias="interactionId")


class CompareAthletesRequest(ApiModel):
    athlete_ids: list[str] = Field(alias="athleteIds", min_length=1)


class AnalistaExplanationResponse(ApiModel):
    athlete_id: str = Field(alias="athleteId")
    athlete_name: str = Field(alias="athleteName")
    as_of: str = Field(alias="asOf")
    explanation: str
    limits: str
    sample_size: int = Field(alias="sampleSize")
    interaction_id: str = Field(alias="interactionId")
    cached: bool


class AiFeedbackRequest(ApiModel):
    rating: str


class AiFeedbackResponse(ApiModel):
    interaction_id: str = Field(alias="interactionId")
    rating: str
    feedback_at: str = Field(alias="feedbackAt")
