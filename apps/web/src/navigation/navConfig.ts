import type { NavItemDefinition, Permission } from "@fantappero/contracts";

/** Declarative navigation catalog for member app and global admin panel. */
export const APP_NAV_ITEMS: readonly NavItemDefinition[] = [
  {
    id: "leagues",
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
    id: "standings",
    path: "/classifica",
    requiredPermissions: ["matchday:view"],
    surface: "app",
  },
  {
    id: "roster",
    path: "/rosa",
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
    id: "auction",
    path: "/asta",
    requiredPermissions: ["market:view"],
    surface: "app",
  },
  {
    id: "market",
    path: "/mercato",
    requiredPermissions: ["market:view"],
    surface: "app",
  },
  {
    id: "league-admin",
    path: "/lega/amministrazione",
    requiredPermissions: ["league:admin"],
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
];

export const NAV_LABELS: Record<string, string> = {
  leagues: "Leghe",
  matchday: "Turni",
  standings: "Classifica",
  roster: "Rosa",
  formation: "Formazione",
  auction: "Asta",
  market: "Mercato",
  "league-admin": "Admin lega",
  profile: "Profilo",
  "admin-home": "Pannello",
  "admin-leagues": "Leghe globali",
  "admin-users": "Utenti",
};

export type ResolvedNavItem = NavItemDefinition & {
  label: string;
  active: boolean;
};

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
