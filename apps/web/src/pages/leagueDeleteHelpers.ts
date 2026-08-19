import type { LeagueState } from "@fantappero/contracts";

/** Hard-delete allowed only before auction/season start (EP03-05-EXT). */
export const DELETABLE_LEAGUE_STATES = new Set<LeagueState>(["draft", "configuring"]);

export function isLeagueDeletable(state: LeagueState | undefined): boolean {
  return state !== undefined && DELETABLE_LEAGUE_STATES.has(state);
}
