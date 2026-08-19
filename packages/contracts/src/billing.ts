/** Entitlements, subscription webhook, audit log, Pro export contracts (EP11). */

export type SubscriptionPlan = "free" | "pro";

export interface EntitlementStatus {
  plan: SubscriptionPlan;
  activeUntil: string | null;
  aiDailyLimit: number;
}

export interface AuditLogEntry {
  id: string;
  occurredAt: string;
  actorId: string;
  actorDisplayName: string | null;
  action: string;
  details: Record<string, unknown> | null;
}

export interface AuditLogList {
  items: AuditLogEntry[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface LeagueProExport {
  leagueId: string;
  generatedAt: string;
  standings: unknown[];
  auditEventsCount: number;
}
