/** Admin panel contracts — platform operator only (EP11-04a / EP11-04b). */

import type { FantasyRole } from "./leagues.js";

export type PlatformRole = "user" | "operator";

export interface AdminOverview {
  operatorId: string;
  operatorDisplayName: string;
  environment: string;
  usersCount: number;
  operatorsCount: number;
  leaguesCount: number;
}

export interface AdminUser {
  id: string;
  email: string;
  displayName: string;
  platformRole: PlatformRole;
  createdAt: string;
}

export interface PaginatedAdminUsers {
  items: AdminUser[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface AdminLeague {
  id: string;
  name: string;
  state: string;
  ownerDisplayName: string | null;
  createdAt: string;
}

export interface PaginatedAdminLeagues {
  items: AdminLeague[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface AdminListoneEntry {
  athleteId: string;
  canonicalName: string;
  seasonYear: number;
  officialRole: FantasyRole;
  providerPositionRaw: string | null;
  mappingVersion: string;
  clubId: string | null;
  clubName: string | null;
}

export interface AdminListoneRefreshCounters {
  athletesCreated: number;
  athletesUpdated: number;
  membershipsCreated: number;
  membershipsUpdated: number;
  transfersCreated: number;
  listoneCreated: number;
  listoneUpdated: number;
  listoneUnchanged: number;
  listoneSkippedUnmapped: number;
  catalogSynced: boolean;
}

export interface AdminListoneRefreshResult {
  seasonYear: number;
  mappingVersion: string;
  refreshedAt: string;
  message: string;
  counters: AdminListoneRefreshCounters;
}

export interface AdminListoneRefreshJob {
  jobId: string;
  status: string;
  message: string;
}

export interface AdminListoneRefreshProgress {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  percent: number;
  stage: string;
  message: string;
  errorCode?: string | null;
  result?: AdminListoneRefreshResult | null;
}

/**
 * Pannello operatore — turni, calendario, formazioni IA (EP-turni-automazione).
 *
 * Riga di sintesi per una lega attiva: il "turno corrente" è quello aperto,
 * o il primo programmato, o l'ultimo esistente se la lega è a fine stagione.
 */
export interface AdminLeagueTurnStatus {
  leagueId: string;
  leagueName: string;
  currentRoundId: string | null;
  currentRoundNumber: number | null;
  currentRoundStatus: string | null;
  homologationStatus: string | null;
  calendarUpdatedAt: string | null;
}

/** Esito di "Sincronizza turni" massivo (tutte le leghe attive). */
export interface AdminTurniSyncResult {
  leagues: number;
  created: number;
  opened: number;
  upgraded: number;
  duplicates: number;
  waiting: number;
}

/** Esito di "Genera formazioni AI" massivo (tutte le leghe attive). */
export interface AdminAiLineupsSyncResult {
  rounds: number;
  teamsUpdated: number;
  teamsSkipped: number;
}

export interface AdminCalendarSyncJob {
  jobId: string;
  status: string;
  message: string;
}

/** Esito di "Genera calendario" massivo (tutte le leghe attive). */
export interface AdminCalendarSyncResult {
  leagues: number;
  refreshed: number;
  failed: number;
  fixturesCreated: number;
  fixturesUpdated: number;
  roundsRealigned: number;
  roundsRemoved: number;
}

export interface AdminCalendarSyncProgress {
  jobId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  percent: number;
  stage: string;
  message: string;
  errorCode?: string | null;
  result?: AdminCalendarSyncResult | null;
}
