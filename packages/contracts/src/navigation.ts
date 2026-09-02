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

/**
 * Collapsible group of nav items (EP13-P01). Visibility is derived: a group is
 * rendered only when at least one of its items survives the permission filter.
 */
export interface NavGroupDefinition {
  id: string;
  /** Ids of `NavItemDefinition` entries in this group, in display order. */
  itemIds: readonly string[];
}

/** Breadcrumb segment (label from app layer). */
export interface BreadcrumbItem {
  label: string;
  href?: string;
}
