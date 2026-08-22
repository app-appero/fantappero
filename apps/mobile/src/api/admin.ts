import type {
  AdminListoneEntry,
  AdminListoneRefreshJob,
  AdminListoneRefreshProgress,
  AdminListoneRefreshResult,
  AdminOverview,
  AdminUser,
  PaginatedAdminLeagues,
  PaginatedAdminUsers,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

/** Mobile port of `apps/web/src/api/admin.ts` — global operator panel (EP11-04a/b). */

export function fetchAdminOverview(accessToken: string): Promise<AdminOverview> {
  return apiRequest<AdminOverview>("/admin/overview", { accessToken });
}

export function fetchAdminUsers(
  accessToken: string,
  options: { query?: string; page?: number } = {},
): Promise<PaginatedAdminUsers> {
  const params = new URLSearchParams();
  if (options.query) {
    params.set("query", options.query);
  }
  if (options.page) {
    params.set("page", String(options.page));
  }
  const qs = params.toString();
  return apiRequest<PaginatedAdminUsers>(`/admin/users${qs ? `?${qs}` : ""}`, { accessToken });
}

export function promoteOperator(accessToken: string, userId: string): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/admin/users/${userId}/promote`, {
    accessToken,
    method: "POST",
  });
}

export function revokeOperator(accessToken: string, userId: string): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/admin/users/${userId}/revoke`, {
    accessToken,
    method: "POST",
  });
}

export function fetchAdminLeagues(
  accessToken: string,
  options: { query?: string; page?: number } = {},
): Promise<PaginatedAdminLeagues> {
  const params = new URLSearchParams();
  if (options.query) {
    params.set("query", options.query);
  }
  if (options.page) {
    params.set("page", String(options.page));
  }
  const qs = params.toString();
  return apiRequest<PaginatedAdminLeagues>(`/admin/leagues${qs ? `?${qs}` : ""}`, { accessToken });
}

export function fetchAdminListone(
  accessToken: string,
  seasonYear: number,
): Promise<AdminListoneEntry[]> {
  const params = new URLSearchParams({ seasonYear: String(seasonYear) });
  return apiRequest<AdminListoneEntry[]>(`/admin/listone?${params}`, { accessToken });
}

export function startAdminListoneRefresh(
  accessToken: string,
  seasonYear: number,
): Promise<AdminListoneRefreshJob> {
  const params = new URLSearchParams({ seasonYear: String(seasonYear) });
  return apiRequest<AdminListoneRefreshJob>(`/admin/listone/aggiorna?${params}`, {
    accessToken,
    method: "POST",
  });
}

export function fetchAdminListoneRefreshProgress(
  accessToken: string,
  jobId: string,
): Promise<AdminListoneRefreshProgress> {
  return apiRequest<AdminListoneRefreshProgress>(`/admin/listone/aggiorna/${jobId}`, {
    accessToken,
  });
}

export async function refreshAdminListone(
  accessToken: string,
  seasonYear: number,
  options?: {
    onProgress?: (progress: AdminListoneRefreshProgress) => void;
    pollIntervalMs?: number;
  },
): Promise<AdminListoneRefreshResult> {
  const started = await startAdminListoneRefresh(accessToken, seasonYear);
  if (!started.jobId) {
    throw new Error("Aggiornamento avviato ma senza jobId. Ricarica la schermata e riprova.");
  }
  const pollIntervalMs = options?.pollIntervalMs ?? 800;
  for (;;) {
    const progress = await fetchAdminListoneRefreshProgress(accessToken, started.jobId);
    options?.onProgress?.(progress);
    if (progress.status === "completed") {
      if (!progress.result) {
        throw new Error("Aggiornamento completato senza risultato.");
      }
      return progress.result;
    }
    if (progress.status === "failed") {
      throw new Error(
        progress.message ||
          "Aggiornamento listone non riuscito (controlla quota API-Football / worker).",
      );
    }
    await new Promise((resolve) => {
      setTimeout(resolve, pollIntervalMs);
    });
  }
}
