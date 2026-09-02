import type {
  CreateNamedLeagueInviteRequest,
  FantasyCoachDirectoryItem,
  FantasyCoachProfile,
  PendingInviteCount,
  NamedLeagueInvite,
  PaginatedFantasyCoachDirectory,
  RespondedNamedLeagueInvite,
  UserType,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

export type { FantasyCoachDirectoryItem, PaginatedFantasyCoachDirectory, UserType };

export function fetchManagerDirectory(
  accessToken: string,
  leagueId: string,
  options: {
    query?: string;
    userType?: UserType;
    available?: boolean;
    page?: number;
    pageSize?: number;
  } = {},
): Promise<PaginatedFantasyCoachDirectory> {
  const params = new URLSearchParams();
  if (options.query) params.set("search", options.query);
  if (options.userType) params.set("userType", options.userType);
  if (options.available !== undefined) params.set("available", String(options.available));
  params.set("page", String(options.page ?? 1));
  params.set("pageSize", String(options.pageSize ?? 12));
  return apiRequest<PaginatedFantasyCoachDirectory>(
    `/leagues/${leagueId}/amministrazione/fantallenatori?${params.toString()}`,
    { accessToken },
  );
}

/** Profilo storico limitato di un fantallenatore (EP13-P06). */
export function fetchCoachProfile(
  accessToken: string,
  leagueId: string,
  userId: string,
  options: { page?: number; pageSize?: number } = {},
): Promise<FantasyCoachProfile> {
  const params = new URLSearchParams();
  params.set("page", String(options.page ?? 1));
  params.set("pageSize", String(options.pageSize ?? 20));
  return apiRequest<FantasyCoachProfile>(
    `/leagues/${leagueId}/amministrazione/fantallenatori/${userId}?${params.toString()}`,
    { accessToken },
  );
}

/** Conteggio inviti pendenti per il badge (EP13-P07). */
export function fetchPendingInviteCount(accessToken: string): Promise<PendingInviteCount> {
  return apiRequest<PendingInviteCount>("/leagues/inviti-ricevuti/conteggio", { accessToken });
}

export function createNamedLeagueInvite(
  accessToken: string,
  leagueId: string,
  recipientUserId: string,
): Promise<NamedLeagueInvite> {
  const body: CreateNamedLeagueInviteRequest = { recipientUserId };
  return apiRequest<NamedLeagueInvite>(
    `/leagues/${leagueId}/amministrazione/inviti-nominativi`,
    {
      method: "POST",
      accessToken,
      body,
    },
  );
}

export function fetchReceivedNamedInvites(
  accessToken: string,
): Promise<NamedLeagueInvite[]> {
  return apiRequest<NamedLeagueInvite[]>("/leagues/inviti-ricevuti", { accessToken });
}

export function acceptReceivedNamedInvite(
  accessToken: string,
  inviteId: string,
): Promise<RespondedNamedLeagueInvite> {
  return apiRequest<RespondedNamedLeagueInvite>(`/leagues/inviti-ricevuti/${inviteId}/accetta`, {
    method: "POST",
    accessToken,
  });
}

export function declineReceivedNamedInvite(
  accessToken: string,
  inviteId: string,
): Promise<RespondedNamedLeagueInvite> {
  return apiRequest<RespondedNamedLeagueInvite>(`/leagues/inviti-ricevuti/${inviteId}/rifiuta`, {
    method: "POST",
    accessToken,
  });
}
