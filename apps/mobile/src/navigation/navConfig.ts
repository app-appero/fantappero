import type { Permission } from "@fantappero/contracts";
import type { NavGroupDefinition, NavItemDefinition } from "@fantappero/contracts";

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

/** Gruppo "Lega" — identico al web `APP_NAV_GROUPS` (EP13-P01). */
export const MOBILE_NAV_GROUPS: readonly NavGroupDefinition[] = [
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

export type MobileNavSection =
  | { kind: "item"; item: ResolvedMobileNavItem }
  | { kind: "group"; id: string; label: string; items: ResolvedMobileNavItem[] };

/**
 * Ordina le voci visibili in sezioni per il drawer: il gruppo prende la
 * posizione della sua prima voce visibile, le altre restano indipendenti.
 * Un gruppo senza voci autorizzate non viene prodotto.
 */
export function buildMobileNavSections(
  items: readonly ResolvedMobileNavItem[],
  groups: readonly NavGroupDefinition[] = MOBILE_NAV_GROUPS,
): MobileNavSection[] {
  const groupByItemId = new Map<string, NavGroupDefinition>();
  for (const group of groups) {
    for (const itemId of group.itemIds) {
      groupByItemId.set(itemId, group);
    }
  }

  const sections: MobileNavSection[] = [];
  const groupSections = new Map<string, Extract<MobileNavSection, { kind: "group" }>>();

  for (const item of items) {
    const group = groupByItemId.get(item.id);
    if (!group) {
      sections.push({ kind: "item", item });
      continue;
    }
    let section = groupSections.get(group.id);
    if (!section) {
      section = {
        kind: "group",
        id: group.id,
        label: NAV_GROUP_LABELS[group.id] ?? group.id,
        items: [],
      };
      groupSections.set(group.id, section);
      sections.push(section);
    }
    section.items.push(item);
  }

  for (const [groupId, section] of groupSections) {
    const order = groups.find((group) => group.id === groupId)?.itemIds ?? [];
    section.items.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
  }

  return sections;
}
