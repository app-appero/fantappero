import type { Permission } from "./auth.js";

/** Navigation surface — app (member), league admin tools, or global operator panel. */
export type NavSurface = "app" | "admin";

/** Declarative nav item used by web and mobile shells (labels supplied by apps). */
export interface NavItemDefinition {
  id: string;
  /** Route path pattern (may include :params). */
  path: string;
  /** Permissions required to show and access this item (all must be granted). */
  requiredPermissions: readonly Permission[];
  /** Which layout shell renders this item. */
  surface: NavSurface;
}

/** Breadcrumb segment (label from app layer). */
export interface BreadcrumbItem {
  label: string;
  href?: string;
}
