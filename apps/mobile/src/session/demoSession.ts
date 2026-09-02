import {
  type LeagueSummary,
  type PermissionContext,
  type SessionUser,
} from "@fantappero/contracts";

export function buildPermissionContext(
  user: SessionUser,
  activeLeagueId: string | null,
  leagues: readonly LeagueSummary[],
): PermissionContext {
  const activeLeague = leagues.find((league) => league.id === activeLeagueId) ?? null;
  return { user, activeLeague };
}
