import type { Permission } from "@fantappero/contracts";
import type { NavItemDefinition } from "@fantappero/contracts";

/**
 * Catalogo drawer mobile — allineato a `apps/web` APP_NAV_ITEMS
 * (stesso ordine ed etichette; permessi identici).
 */
export const MOBILE_DRAWER_NAV_ITEMS: readonly NavItemDefinition[] = [
  {
    id: "leagues",
    path: "/leghe",
    requiredPermissions: ["league:view"],
    surface: "app",
  },
  {
    id: "league-home",
    path: "/lega/home",
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
    id: "waiver",
    path: "/svincoli",
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

/** @deprecated Usare MOBILE_DRAWER_NAV_ITEMS — alias per test/import legacy. */
export const MOBILE_NAV_ITEMS = MOBILE_DRAWER_NAV_ITEMS;

/** Global operator panel — separate admin stack. */
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
  "league-home": "Home lega",
  "manager-directory": "Fantallenatori",
  "received-invites": "Inviti",
  matchday: "Turni",
  standings: "Classifica",
  roster: "Rosa",
  formation: "Formazione",
  auction: "Asta",
  waiver: "Svincolati",
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
