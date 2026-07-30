import {
  type LeagueSummary,
  type PermissionContext,
  type SessionUser,
} from "@fantappero/contracts";

export const DEMO_LEAGUES: readonly LeagueSummary[] = [
  { id: "lega-demo", name: "Lega Demo", role: "member" },
  { id: "lega-admin", name: "Lega Amici", role: "league_admin" },
];

export const DEMO_MEMBER: SessionUser = {
  id: "user-demo",
  displayName: "Marco Rossi",
  globalRole: "member",
};

export function buildPermissionContext(
  user: SessionUser,
  activeLeagueId: string | null,
  leagues: readonly LeagueSummary[] = DEMO_LEAGUES,
): PermissionContext {
  const activeLeague = leagues.find((league) => league.id === activeLeagueId) ?? null;
  return { user, activeLeague };
}
