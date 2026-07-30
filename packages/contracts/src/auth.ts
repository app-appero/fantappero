/** Auth and permission contracts (EPUI-03 — ready for EP02-03 server integration). */

/** Platform-wide role assigned to the user account. */
export type GlobalRole = "member" | "global_operator";

/** Role within a specific private league. */
export type LeagueRole = "member" | "league_admin";

/**
 * Fine-grained permissions used by navigation and feature gates.
 * Server remains authoritative; clients use these for UX filtering only.
 */
export type Permission =
  | "league:view"
  | "league:admin"
  | "roster:view"
  | "roster:edit"
  | "market:view"
  | "market:manage"
  | "matchday:view"
  | "profile:view"
  | "global:operate";

/** Minimal session snapshot exposed to clients after authentication. */
export interface SessionUser {
  id: string;
  displayName: string;
  globalRole: GlobalRole;
}

/** League the user belongs to, with role for permission resolution. */
export interface LeagueSummary {
  id: string;
  name: string;
  role: LeagueRole;
}

/** Resolved permission set for the active session + optional league context. */
export interface PermissionContext {
  user: SessionUser;
  activeLeague: LeagueSummary | null;
}

const GLOBAL_OPERATOR_PERMISSIONS: readonly Permission[] = [
  "league:view",
  "league:admin",
  "roster:view",
  "roster:edit",
  "market:view",
  "market:manage",
  "matchday:view",
  "profile:view",
  "global:operate",
] as const;

const LEAGUE_ADMIN_PERMISSIONS: readonly Permission[] = [
  "league:view",
  "league:admin",
  "roster:view",
  "roster:edit",
  "market:view",
  "market:manage",
  "matchday:view",
  "profile:view",
] as const;

const LEAGUE_MEMBER_PERMISSIONS: readonly Permission[] = [
  "league:view",
  "roster:view",
  "roster:edit",
  "market:view",
  "matchday:view",
  "profile:view",
] as const;

/** Resolve effective permissions from session and active league. */
export function resolvePermissions(context: PermissionContext): Set<Permission> {
  if (context.user.globalRole === "global_operator") {
    return new Set(GLOBAL_OPERATOR_PERMISSIONS);
  }

  const leagueRole = context.activeLeague?.role;
  const base =
    leagueRole === "league_admin" ? LEAGUE_ADMIN_PERMISSIONS : LEAGUE_MEMBER_PERMISSIONS;

  return new Set(base);
}

/** Returns true when every required permission is present in the context. */
export function hasPermissions(
  context: PermissionContext,
  required: readonly Permission[],
): boolean {
  if (required.length === 0) {
    return true;
  }
  const granted = resolvePermissions(context);
  return required.every((permission) => granted.has(permission));
}

/** Returns true when at least one required permission is present. */
export function hasAnyPermission(
  context: PermissionContext,
  required: readonly Permission[],
): boolean {
  if (required.length === 0) {
    return true;
  }
  const granted = resolvePermissions(context);
  return required.some((permission) => granted.has(permission));
}
