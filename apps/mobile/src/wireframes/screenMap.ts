import type { WireframeScreenId } from "@fantappero/contracts";

/** Maps tab/stack route keys to wireframe catalog entries. */
export const ROUTE_TO_WIREFRAME: Record<string, WireframeScreenId> = {
  Auth: "auth",
  LeagueHome: "league-dashboard",
  LeagueAdmin: "league-config",
  Matchday: "matchday",
  Standings: "standings",
  Roster: "roster",
  Formation: "formation",
  Auction: "auction",
  Market: "market",
  AdminHome: "operator-panel",
  AdminLeagues: "operator-panel",
  AdminUsers: "operator-panel",
};

export function wireframeIdForRoute(routeName: string): WireframeScreenId | null {
  return ROUTE_TO_WIREFRAME[routeName] ?? null;
}
