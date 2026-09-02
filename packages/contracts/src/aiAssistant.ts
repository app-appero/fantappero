/** AI-assisted advice contracts — advisory only, never auto-applied (EP10). */

export interface LineupSuggestion {
  starterAthleteId: string;
  starterName: string;
  benchAthleteId: string;
  benchName: string;
  reason: string;
}

export interface ViceallenatoreAdvice {
  suggestions: LineupSuggestion[];
  modificationAllowed: boolean;
  message: string | null;
  interactionId: string | null;
}

export interface AthleteComparisonRow {
  athleteId: string;
  name: string;
  role: string | null;
  avgRating: number | null;
  recentMinutesAvg: number | null;
  injured: boolean | null;
  isFreeAgentInLeague: boolean | null;
  nextOpponentName: string | null;
}

export interface OsservatoreResult {
  rows: AthleteComparisonRow[];
  interactionId: string;
}

export interface CompareAthletesRequest {
  athleteIds: string[];
}

export interface AnalistaExplanation {
  athleteId: string;
  athleteName: string;
  asOf: string;
  explanation: string;
  limits: string;
  sampleSize: number;
  interactionId: string;
  cached: boolean;
}

export type AiFeedbackRatingValue = "up" | "down";

export interface AiFeedbackRequest {
  rating: AiFeedbackRatingValue;
}

export interface AiFeedbackResponse {
  interactionId: string;
  rating: AiFeedbackRatingValue;
  feedbackAt: string;
}
