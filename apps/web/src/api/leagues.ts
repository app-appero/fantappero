import type {
  AcceptedLeagueInvite,
  AcceptLeagueInviteRequest,
  CompetitionSummary,
  CreatedLeagueInvite,
  CreateLeagueInviteRequest,
  CreateLeagueRequest,
  LeagueAdminPanel,
  LeagueCalendar,
  LeagueDetail,
  LeagueInvite,
  LeagueLifecycle,
  LeagueListoneEntry,
  LeagueListoneRefreshResult,
  LeagueMember,
  LeagueRules,
  LeagueSummary,
  TransitionLeagueStateRequest,
  UpdateLeagueRulesRequest,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

export function fetchCompetitions(accessToken: string): Promise<CompetitionSummary[]> {
  return apiRequest<CompetitionSummary[]>("/leagues/competitions", { accessToken });
}

export function fetchMyLeagues(accessToken: string): Promise<LeagueSummary[]> {
  return apiRequest<LeagueSummary[]>("/leagues/mine", { accessToken });
}

export function createLeague(
  accessToken: string,
  payload: CreateLeagueRequest,
): Promise<LeagueDetail> {
  return apiRequest<LeagueDetail>("/leagues", {
    method: "POST",
    accessToken,
    body: payload,
  });
}

export function fetchLeagueAdminPanel(
  accessToken: string,
  leagueId: string,
): Promise<LeagueAdminPanel> {
  return apiRequest<LeagueAdminPanel>(`/leagues/${leagueId}/amministrazione`, { accessToken });
}

export function updateLeagueRules(
  accessToken: string,
  leagueId: string,
  payload: UpdateLeagueRulesRequest,
): Promise<LeagueRules> {
  return apiRequest<LeagueRules>(`/leagues/${leagueId}/amministrazione/regolamento`, {
    method: "PUT",
    accessToken,
    body: payload,
  });
}

export function transitionLeagueState(
  accessToken: string,
  leagueId: string,
  payload: TransitionLeagueStateRequest,
): Promise<LeagueLifecycle> {
  return apiRequest<LeagueLifecycle>(`/leagues/${leagueId}/amministrazione/stato`, {
    method: "POST",
    accessToken,
    body: payload,
  });
}

export function fetchLeagueMembers(
  accessToken: string,
  leagueId: string,
): Promise<LeagueMember[]> {
  return apiRequest<LeagueMember[]>(`/leagues/${leagueId}/amministrazione/partecipanti`, {
    accessToken,
  });
}

export function transferLeagueAdmin(
  accessToken: string,
  leagueId: string,
  userId: string,
): Promise<LeagueMember> {
  return apiRequest<LeagueMember>(
    `/leagues/${leagueId}/amministrazione/partecipanti/${userId}/trasferimento-admin`,
    { method: "POST", accessToken },
  );
}

export function removeLeagueMember(
  accessToken: string,
  leagueId: string,
  userId: string,
): Promise<LeagueMember> {
  return apiRequest<LeagueMember>(
    `/leagues/${leagueId}/amministrazione/partecipanti/${userId}`,
    { method: "DELETE", accessToken },
  );
}

export function fetchLeagueInvites(
  accessToken: string,
  leagueId: string,
): Promise<LeagueInvite[]> {
  return apiRequest<LeagueInvite[]>(`/leagues/${leagueId}/amministrazione/inviti`, {
    accessToken,
  });
}

export function createLeagueInvite(
  accessToken: string,
  leagueId: string,
  payload: CreateLeagueInviteRequest,
): Promise<CreatedLeagueInvite> {
  return apiRequest<CreatedLeagueInvite>(`/leagues/${leagueId}/amministrazione/inviti`, {
    method: "POST",
    accessToken,
    body: payload,
  });
}

export function revokeLeagueInvite(
  accessToken: string,
  leagueId: string,
  inviteId: string,
): Promise<LeagueInvite> {
  return apiRequest<LeagueInvite>(
    `/leagues/${leagueId}/amministrazione/inviti/${inviteId}`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}

export function acceptLeagueInvite(
  accessToken: string,
  payload: AcceptLeagueInviteRequest,
): Promise<AcceptedLeagueInvite> {
  return apiRequest<AcceptedLeagueInvite>("/leagues/inviti/accetta", {
    method: "POST",
    accessToken,
    body: payload,
  });
}

export function fetchLeagueCalendarAdmin(
  accessToken: string,
  leagueId: string,
): Promise<LeagueCalendar | null> {
  return apiRequest<LeagueCalendar | null>(`/leagues/${leagueId}/amministrazione/calendario`, {
    accessToken,
  });
}

export function generateLeagueCalendar(
  accessToken: string,
  leagueId: string,
): Promise<LeagueCalendar> {
  return apiRequest<LeagueCalendar>(`/leagues/${leagueId}/amministrazione/calendario/genera`, {
    method: "POST",
    accessToken,
  });
}

export function confirmLeagueCalendar(
  accessToken: string,
  leagueId: string,
): Promise<LeagueCalendar> {
  return apiRequest<LeagueCalendar>(`/leagues/${leagueId}/amministrazione/calendario/conferma`, {
    method: "POST",
    accessToken,
  });
}

export function fetchLeagueListone(
  accessToken: string,
  leagueId: string,
  currentRound = 0,
): Promise<LeagueListoneEntry[]> {
  const params = new URLSearchParams({ currentRound: String(currentRound) });
  return apiRequest<LeagueListoneEntry[]>(`/leagues/${leagueId}/listone?${params}`, {
    accessToken,
  });
}

export function refreshLeagueListone(
  accessToken: string,
  leagueId: string,
): Promise<LeagueListoneRefreshResult> {
  return apiRequest<LeagueListoneRefreshResult>(
    `/leagues/${leagueId}/amministrazione/listone/aggiorna`,
    {
      method: "POST",
      accessToken,
    },
  );
}

