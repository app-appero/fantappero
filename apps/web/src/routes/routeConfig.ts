import type { Permission } from "@fantappero/contracts";

export type RouteLayout = "none" | "app" | "admin";

/** Declarative route registry for the responsive app shell (EPUI-05). */
export type AppRouteDefinition = {
  id: string;
  path: string;
  layout: RouteLayout;
  requiredPermissions?: readonly Permission[];
  requireGlobalOperator?: boolean;
};

export const APP_ROUTE_DEFINITIONS: readonly AppRouteDefinition[] = [
  { id: "auth-login", path: "/accedi", layout: "none" },
  { id: "auth-register", path: "/accedi/registrati", layout: "none" },
  { id: "auth-forgot", path: "/accedi/recupera", layout: "none" },
  { id: "auth-reset", path: "/accedi/reimposta-password", layout: "none" },
  { id: "auth-verify", path: "/accedi/verifica", layout: "none" },
  { id: "leagues", path: "/leghe", layout: "app", requiredPermissions: ["league:view"] },
  {
    id: "league-create",
    path: "/leghe/crea",
    layout: "app",
    requiredPermissions: ["league:view"],
  },
  {
    id: "league-invite",
    path: "/leghe/invito",
    layout: "app",
    requiredPermissions: ["league:view"],
  },
  {
    id: "league-home",
    path: "/lega/home",
    layout: "app",
    requiredPermissions: ["league:view"],
  },
  {
    id: "manager-directory",
    path: "/fantallenatori",
    layout: "app",
    requiredPermissions: ["league:admin"],
  },
  {
    id: "received-invites",
    path: "/inviti",
    layout: "app",
    requiredPermissions: ["league:view"],
  },
  { id: "matchday", path: "/turni", layout: "app", requiredPermissions: ["matchday:view"] },
  { id: "standings", path: "/classifica", layout: "app", requiredPermissions: ["matchday:view"] },
  { id: "roster", path: "/rosa", layout: "app", requiredPermissions: ["roster:view"] },
  { id: "formation", path: "/formazione", layout: "app", requiredPermissions: ["roster:view"] },
  { id: "auction", path: "/asta", layout: "app", requiredPermissions: ["market:view"] },
  { id: "market", path: "/mercato", layout: "app", requiredPermissions: ["market:view"] },
  {
    id: "league-admin",
    path: "/lega/amministrazione",
    layout: "app",
    requiredPermissions: ["league:admin"],
  },
  { id: "profile", path: "/profilo", layout: "app", requiredPermissions: ["profile:view"] },
  { id: "dev-design-system", path: "/dev/design-system", layout: "app" },
  { id: "dev-wireframes", path: "/dev/wireframes", layout: "app" },
  {
    id: "admin-home",
    path: "/admin",
    layout: "admin",
    requiredPermissions: ["global:operate"],
    requireGlobalOperator: true,
  },
  {
    id: "admin-leagues",
    path: "/admin/leghe",
    layout: "admin",
    requiredPermissions: ["global:operate"],
    requireGlobalOperator: true,
  },
  {
    id: "admin-users",
    path: "/admin/utenti",
    layout: "admin",
    requiredPermissions: ["global:operate"],
    requireGlobalOperator: true,
  },
] as const;

/** Root path aliases handled outside the registry. */
export const ROOT_ALIASES = ["/"] as const;
