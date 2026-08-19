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
