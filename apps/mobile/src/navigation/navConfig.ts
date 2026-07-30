import type { NavItemDefinition } from "@fantappero/contracts";

/** Mobile tab bar catalog — labels live in NAV_LABELS below. */
export const MOBILE_NAV_ITEMS: readonly NavItemDefinition[] = [
  {
    id: "matchday",
    path: "/turni",
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
    id: "market",
    path: "/mercato",
    requiredPermissions: ["market:view"],
    surface: "app",
  },
  {
    id: "leagues",
    path: "/leghe",
    requiredPermissions: ["league:view"],
    surface: "app",
  },
  {
    id: "profile",
    path: "/profilo",
    requiredPermissions: ["profile:view"],
    surface: "app",
  },
];

export const NAV_LABELS: Record<string, string> = {
  matchday: "Turni",
  standings: "Classifica",
  roster: "Rosa",
  formation: "Formazione",
  auction: "Asta",
  market: "Mercato",
  leagues: "Leghe",
  profile: "Profilo",
};
