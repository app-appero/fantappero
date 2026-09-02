import type { NavGroupDefinition, NavItemDefinition, Permission } from "@fantappero/contracts";

/** Declarative navigation catalog for member app and global admin panel. */
export const APP_NAV_ITEMS: readonly NavItemDefinition[] = [
  {
    id: "league-hub",
    path: "/leghe",
    requiredPermissions: ["league:view"],
    surface: "app",
  },
  {
    id: "matchday",
    path: "/turni",
    requiredPermissions: ["matchday:view"],
    surface: "app",
  },
  {
    id: "manager-directory",
    path: "/fantallenatori",
    requiredPermissions: ["league:admin"],
    surface: "app",
  },
  {
    id: "received-invites",
    path: "/inviti",
    requiredPermissions: ["league:view"],
    surface: "app",
  },
  {
    id: "standings",
    path: "/classifica",
    requiredPermissions: ["matchday:view"],
    surface: "app",
  },
  {
    id: "market-hub",
    path: "/mercato",
    requiredPermissions: ["roster:view"],
    surface: "app",
  },
  {
    id: "formation",
    path: "/formazione",
    requiredPermissions: ["roster:view"],
    surface: "app",
  },
  {
    id: "profile",
    path: "/profilo",
    requiredPermissions: ["profile:view"],
    surface: "app",
  },
];

export const ADMIN_NAV_ITEMS: readonly NavItemDefinition[] = [
  {
    id: "admin-home",
    path: "/admin",
    requiredPermissions: ["global:operate"],
    surface: "admin",
  },
  {
    id: "admin-leagues",
    path: "/admin/leghe",
    requiredPermissions: ["global:operate"],
    surface: "admin",
  },
  {
    id: "admin-users",
    path: "/admin/utenti",
    requiredPermissions: ["global:operate"],
    surface: "admin",
  },
  {
    id: "admin-listone",
    path: "/admin/listone",
    requiredPermissions: ["global:operate"],
    surface: "admin",
  },
  {
    id: "admin-turni",
    path: "/admin/turni",
    requiredPermissions: ["global:operate"],
    surface: "admin",
  },
];

/**
 * "Lega" e "Mercato" (movimento giocatori) sono pagine a tab interne — le
 * destinazioni correlate (Le mie leghe/Home lega/Amministrazione,
 * Rosa/Asta/Svincolati/Mercato) non hanno più voci di menu separate.
 */
export const APP_NAV_GROUPS: readonly NavGroupDefinition[] = [];

export const NAV_GROUP_LABELS: Record<string, string> = {};

export const NAV_LABELS: Record<string, string> = {
  "league-hub": "Lega",
  "manager-directory": "Fantallenatori",
  "received-invites": "Inviti",
  matchday: "Turni",
  standings: "Classifica",
  "market-hub": "Mercato",
  formation: "Formazione",
  profile: "Profilo",
  "admin-home": "Pannello",
  "admin-leagues": "Leghe globali",
  "admin-users": "Utenti",
  "admin-listone": "Listone",
  "admin-turni": "Turni",
};

/**
 * Etichette compatte per la bottom nav (<768px), dove la larghezza per voce è
 * ~6rem. La sidebar e i test usano `NAV_LABELS`.
 */
export const NAV_SHORT_LABELS: Record<string, string> = {
  "league-hub": "Lega",
  "market-hub": "Mercato",
};

export type ResolvedNavItem = NavItemDefinition & {
  label: string;
  active: boolean;
};

export type ResolvedNavGroup = {
  id: string;
  label: string;
  itemIds: readonly string[];
};

/** Gruppi con label risolta; la visibilità è derivata dalle voci filtrate. */
export function resolveNavGroups(
  groups: readonly NavGroupDefinition[] = APP_NAV_GROUPS,
): ResolvedNavGroup[] {
  return groups.map((group) => ({
    id: group.id,
    label: NAV_GROUP_LABELS[group.id] ?? group.id,
    itemIds: group.itemIds,
  }));
}

export function filterNavItems(
  items: readonly NavItemDefinition[],
  can: (required: readonly Permission[]) => boolean,
  pathname: string,
): ResolvedNavItem[] {
  return items
    .filter((item) => can(item.requiredPermissions))
    .map((item) => ({
      ...item,
      label: NAV_LABELS[item.id] ?? item.id,
      active: pathname === item.path || pathname.startsWith(`${item.path}/`),
    }));
}
