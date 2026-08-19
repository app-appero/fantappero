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

function asSearchParams(search: string | URLSearchParams): URLSearchParams {
  if (search instanceof URLSearchParams) {
    return search;
  }
  return new URLSearchParams(search);
}

export function buildPermissionContext(
  user: SessionUser,
  activeLeagueId: string | null,
  leagues: readonly LeagueSummary[] = DEMO_LEAGUES,
): PermissionContext {
  const activeLeague = leagues.find((league) => league.id === activeLeagueId) ?? null;
  return { user, activeLeague };
}

/**
 * Query param `?persona=admin` switches the mock league role for local QA of
 * the league-admin wireframes. Real session (member or global operator) comes
 * from the EP02-03 auth API — the demo session can never produce a global
 * operator identity (EP11-04a: `/admin` is gated only by a real
 * `platform_role=operator` session, never by `?persona=`).
 */
export function resolveDemoUser(_search: string | URLSearchParams): SessionUser {
  return DEMO_MEMBER;
}

export function resolveDemoLeagues(search: string | URLSearchParams): readonly LeagueSummary[] {
  const params = asSearchParams(search);
  if (params.get("persona") === "admin") {
    return DEMO_LEAGUES.map((league) =>
      league.id === "lega-admin" ? { ...league, role: "league_admin" as const } : league,
    );
  }
  return DEMO_LEAGUES.map((league) => ({ ...league, role: "member" as const }));
}

export function resolveInitialLeagueId(
  search: string | URLSearchParams,
  leagues: readonly LeagueSummary[],
): string | null {
  const params = asSearchParams(search);
  if (params.get("persona") === "admin") {
    return leagues.find((league) => league.role === "league_admin")?.id ?? leagues[0]?.id ?? null;
  }
  return leagues[0]?.id ?? null;
}
