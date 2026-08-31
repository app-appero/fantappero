import type { NavGroupDefinition, NavItemDefinition, Permission } from "@fantappero/contracts";

/** Declarative navigation catalog for member app and global admin panel. */
export const APP_NAV_ITEMS: readonly NavItemDefinition[] = [
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
 * Gruppo "Lega" (EP13-P01): le tre voci sono correlate ma non equivalenti —
 * "Le mie leghe" sceglie il contesto, "Home lega" mostra la lega attiva,
 * "Amministrazione lega" la modifica. "Turni" resta destinazione primaria
 * indipendente e "Inviti ricevuti" resta fuori perché è account-level.
 */
export const APP_NAV_GROUPS: readonly NavGroupDefinition[] = [
  {
    id: "league",
    itemIds: ["leagues", "league-home", "league-admin"],
  },
];

export const NAV_GROUP_LABELS: Record<string, string> = {
  league: "Lega",
};

export const NAV_LABELS: Record<string, string> = {
  leagues: "Le mie leghe",
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
  "league-admin": "Amministrazione lega",
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
  leagues: "Leghe",
  "league-admin": "Admin lega",
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
