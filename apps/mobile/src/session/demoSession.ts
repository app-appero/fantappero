import {
  type LeagueSummary,
  type PermissionContext,
  type SessionUser,
} from "@fantappero/contracts";

export type DemoPersona = "member" | "admin" | "operator";

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

export function resolveDemoUser(persona: DemoPersona): SessionUser {
  if (persona === "operator") {
    return DEMO_OPERATOR;
  }
  return DEMO_MEMBER;
}

export function resolveDemoLeagues(persona: DemoPersona): readonly LeagueSummary[] {
  if (persona === "admin") {
    return DEMO_LEAGUES.map((league) =>
      league.id === "lega-admin" ? { ...league, role: "league_admin" as const } : league,
    );
  }
  return DEMO_LEAGUES;
}

export function resolveInitialLeagueId(
  persona: DemoPersona,
  leagues: readonly LeagueSummary[],
): string | null {
  if (persona === "admin") {
    return leagues.find((league) => league.role === "league_admin")?.id ?? leagues[0]?.id ?? null;
  }
  return leagues[0]?.id ?? null;
}
