import type { AuditLogList, EntitlementStatus, LeagueProExport } from "@fantappero/contracts";
import { apiRequest } from "./client";

export function fetchMyEntitlement(accessToken: string): Promise<EntitlementStatus> {
  return apiRequest<EntitlementStatus>("/billing/me", { accessToken });
}

export function fetchLeagueAuditLog(
  accessToken: string,
  leagueId: string,
  params: { page?: number; pageSize?: number } = {},
): Promise<AuditLogList> {
  const query = new URLSearchParams();
  if (params.page) {
    query.set("page", String(params.page));
  }
  if (params.pageSize) {
    query.set("pageSize", String(params.pageSize));
  }
  const qs = query.toString();
  return apiRequest<AuditLogList>(`/leagues/${leagueId}/audit${qs ? `?${qs}` : ""}`, {
    accessToken,
  });
}

export function fetchLeagueProExport(
  accessToken: string,
  leagueId: string,
): Promise<LeagueProExport> {
  return apiRequest<LeagueProExport>(`/leagues/${leagueId}/pro/export`, { accessToken });
}
