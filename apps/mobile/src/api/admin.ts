import type {
  AdminAiLineupsSyncResult,
  AdminCalendarSyncJob,
  AdminCalendarSyncProgress,
  AdminCalendarSyncResult,
  AdminHistoricalRepairJob,
  AdminHistoricalRepairProgress,
  AdminHistoricalRepairResult,
  AdminLeagueTurnStatus,
  AdminListoneEntry,
  AdminListoneRefreshJob,
  AdminListoneRefreshProgress,
  AdminListoneRefreshResult,
  AdminOverview,
  AdminRoundCalculationResult,
  AdminTurniSyncResult,
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

// --- Pannello operatore: turni, calendario, formazioni IA (EP-turni-automazione/calcolo) ---

export function fetchAdminLeagueTurnStatus(
  accessToken: string,
): Promise<AdminLeagueTurnStatus[]> {
  return apiRequest<AdminLeagueTurnStatus[]>("/admin/turni/leghe", { accessToken });
}

export function syncAllLeagueTurns(accessToken: string): Promise<AdminTurniSyncResult> {
  return apiRequest<AdminTurniSyncResult>("/admin/turni/sincronizza", {
    accessToken,
    method: "POST",
  });
}

export function generateAllAiLineups(accessToken: string): Promise<AdminAiLineupsSyncResult> {
  return apiRequest<AdminAiLineupsSyncResult>("/admin/formazioni-ia/genera", {
    accessToken,
    method: "POST",
  });
}

export function startCalendarSyncAllLeagues(accessToken: string): Promise<AdminCalendarSyncJob> {
  return apiRequest<AdminCalendarSyncJob>("/admin/calendario/sincronizza", {
    accessToken,
    method: "POST",
  });
}

export function fetchCalendarSyncAllLeaguesProgress(
  accessToken: string,
  jobId: string,
): Promise<AdminCalendarSyncProgress> {
  return apiRequest<AdminCalendarSyncProgress>(`/admin/calendario/sincronizza/${jobId}`, {
    accessToken,
  });
}

export async function syncCalendarForAllLeagues(
  accessToken: string,
  options?: {
    onProgress?: (progress: AdminCalendarSyncProgress) => void;
    pollIntervalMs?: number;
  },
): Promise<AdminCalendarSyncResult> {
  const started = await startCalendarSyncAllLeagues(accessToken);
  if (!started.jobId) {
    throw new Error("Aggiornamento avviato ma senza jobId. Ricarica la schermata e riprova.");
  }
  const pollIntervalMs = options?.pollIntervalMs ?? 800;
  for (;;) {
    const progress = await fetchCalendarSyncAllLeaguesProgress(accessToken, started.jobId);
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
          "Aggiornamento calendario massivo non riuscito (controlla quota API-Football / worker).",
      );
    }
    await new Promise((resolve) => {
      setTimeout(resolve, pollIntervalMs);
    });
  }
}

export function calculateCurrentRoundsAllLeagues(
  accessToken: string,
): Promise<AdminRoundCalculationResult> {
  return apiRequest<AdminRoundCalculationResult>("/admin/turni/calcola-giornata", {
    accessToken,
    method: "POST",
  });
}

export function startHistoricalRepair(
  accessToken: string,
  reason: string,
): Promise<AdminHistoricalRepairJob> {
  return apiRequest<AdminHistoricalRepairJob>("/admin/turni/ricalcola-storico", {
    accessToken,
    method: "POST",
    body: { reason },
  });
}

export function fetchHistoricalRepairProgress(
  accessToken: string,
  jobId: string,
): Promise<AdminHistoricalRepairProgress> {
  return apiRequest<AdminHistoricalRepairProgress>(`/admin/turni/ricalcola-storico/${jobId}`, {
    accessToken,
  });
}

export async function repairHistoricalRounds(
  accessToken: string,
  reason: string,
  options?: {
    onProgress?: (progress: AdminHistoricalRepairProgress) => void;
    pollIntervalMs?: number;
  },
): Promise<AdminHistoricalRepairResult> {
  const started = await startHistoricalRepair(accessToken, reason);
  if (!started.jobId) {
    throw new Error("Ricalcolo avviato ma senza jobId. Ricarica la schermata e riprova.");
  }
  const pollIntervalMs = options?.pollIntervalMs ?? 800;
  for (;;) {
    const progress = await fetchHistoricalRepairProgress(accessToken, started.jobId);
    options?.onProgress?.(progress);
    if (progress.status === "completed") {
      if (!progress.result) {
        throw new Error("Ricalcolo completato senza risultato.");
      }
      return progress.result;
    }
    if (progress.status === "failed") {
      throw new Error(progress.message || "Ricalcolo storico non riuscito.");
    }
    await new Promise((resolve) => {
      setTimeout(resolve, pollIntervalMs);
    });
  }
}
