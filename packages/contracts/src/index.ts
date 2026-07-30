/** Shared API contract types (scaffold — OpenAPI generation comes later). */

export {
  hasAnyPermission,
  hasPermissions,
  resolvePermissions,
} from "./auth.js";
export type {
  GlobalRole,
  LeagueRole,
  LeagueSummary,
  Permission,
  PermissionContext,
  SessionUser,
} from "./auth.js";

export type { BreadcrumbItem, NavItemDefinition, NavSurface } from "./navigation.js";

export {
  SERVICES,
  type HealthResponse,
  type HealthStatus,
  type ServiceId,
  type ServiceInfo,
} from "./health.js";
