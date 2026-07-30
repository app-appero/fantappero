import {
  type LeagueSummary,
  type PermissionContext,
  type SessionUser,
} from "@fantappero/contracts";

/** Demo leagues — replaced by API in EP02-03+. */
export const DEMO_LEAGUES: readonly LeagueSummary[] = [
  { id: "lega-demo", name: "Lega Demo", role: "member" },
  { id: "lega-admin", name: "Lega Amici", role: "league_admin" },
];

export const DEMO_MEMBER: SessionUser = {
  id: "user-demo",
  displayName: "Marco Rossi",
  globalRole: "member",
};

export const DEMO_OPERATOR: SessionUser = {
  id: "op-demo",
  displayName: "Operatore Piattaforma",
  globalRole: "global_operator",
};

export function buildPermissionContext(
  user: SessionUser,
  activeLeagueId: string | null,
  leagues: readonly LeagueSummary[] = DEMO_LEAGUES,
): PermissionContext {
  const activeLeague = leagues.find((league) => league.id === activeLeagueId) ?? null;
  return { user, activeLeague };
}

/**
 * Query param `?persona=operator|admin` switches mock session for local QA.
 * Production session comes from EP02-03 auth API.
 */
export function resolveDemoUser(search: string): SessionUser {
  const params = new URLSearchParams(search);
  const persona = params.get("persona");
  if (persona === "operator") {
    return DEMO_OPERATOR;
  }
  return DEMO_MEMBER;
}

export function resolveDemoLeagues(search: string): readonly LeagueSummary[] {
  const params = new URLSearchParams(search);
  if (params.get("persona") === "admin") {
    return DEMO_LEAGUES.map((league) =>
      league.id === "lega-admin" ? { ...league, role: "league_admin" as const } : league,
    );
  }
  return DEMO_LEAGUES;
}

export function resolveInitialLeagueId(
  search: string,
  leagues: readonly LeagueSummary[],
): string | null {
  const params = new URLSearchParams(search);
  if (params.get("persona") === "admin") {
    return leagues.find((league) => league.role === "league_admin")?.id ?? leagues[0]?.id ?? null;
  }
  return leagues[0]?.id ?? null;
}
