import type {
  AiFeedbackRequest,
  AiFeedbackResponse,
  AnalistaExplanation,
  CompareAthletesRequest,
  OsservatoreResult,
  ViceallenatoreAdvice,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

export function fetchViceallenatoreAdvice(
  accessToken: string,
  leagueId: string,
  roundId: string,
): Promise<ViceallenatoreAdvice> {
  return apiRequest<ViceallenatoreAdvice>(
    `/leagues/${leagueId}/assistente/viceallenatore/${roundId}`,
    { accessToken },
  );
}

export function compareAthletes(
  accessToken: string,
  leagueId: string,
  body: CompareAthletesRequest,
): Promise<OsservatoreResult> {
  return apiRequest<OsservatoreResult>(`/leagues/${leagueId}/assistente/osservatore/confronto`, {
    accessToken,
    method: "POST",
    body,
  });
}

export function fetchFreeAgentTargets(
  accessToken: string,
  leagueId: string,
  params: { role: string; seasonYear: number; limit?: number },
): Promise<OsservatoreResult> {
  const query = new URLSearchParams({
    role: params.role,
    seasonYear: String(params.seasonYear),
  });
  if (params.limit) {
    query.set("limit", String(params.limit));
  }
  return apiRequest<OsservatoreResult>(
    `/leagues/${leagueId}/assistente/osservatore/obiettivi?${query.toString()}`,
    { accessToken },
  );
}

export function fetchAnalistaExplanation(
  accessToken: string,
  leagueId: string,
  athleteId: string,
): Promise<AnalistaExplanation> {
  return apiRequest<AnalistaExplanation>(
    `/leagues/${leagueId}/assistente/analista/${athleteId}`,
    { accessToken },
  );
}

export function submitAiFeedback(
  accessToken: string,
  interactionId: string,
  body: AiFeedbackRequest,
): Promise<AiFeedbackResponse> {
  return apiRequest<AiFeedbackResponse>(`/assistente/interazioni/${interactionId}/feedback`, {
    accessToken,
    method: "POST",
    body,
  });
}
