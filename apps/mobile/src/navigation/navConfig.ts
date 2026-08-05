import type { NavItemDefinition, Permission } from "@fantappero/contracts";

/** Mobile tab bar catalog — member app routes (labels in NAV_LABELS). */
export const MOBILE_NAV_ITEMS: readonly NavItemDefinition[] = [
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
    id: "profile",
    path: "/profilo",
    requiredPermissions: ["profile:view"],
    surface: "app",
  },
];

/** League admin — outside tab bar, reachable from header link. */
export const MOBILE_LEAGUE_ADMIN_ITEM: NavItemDefinition = {
  id: "league-admin",
  path: "/lega/amministrazione",
  requiredPermissions: ["league:admin"],
  surface: "app",
};

/** Global operator panel — separate admin stack, not in member tab bar. */
export const MOBILE_ADMIN_NAV_ITEMS: readonly NavItemDefinition[] = [
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
  auth: "Accedi",
};

export type ResolvedMobileNavItem = NavItemDefinition & {
  label: string;
};

export function filterMobileNavItems(
  items: readonly NavItemDefinition[],
  can: (required: readonly Permission[]) => boolean,
): ResolvedMobileNavItem[] {
  return items
    .filter((item) => can(item.requiredPermissions))
    .map((item) => ({
      ...item,
      label: NAV_LABELS[item.id] ?? item.id,
    }));
}
