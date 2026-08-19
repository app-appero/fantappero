import type { WireframeUiState } from "@fantappero/contracts";

export function resolveAdminInviteState(
  canAdminister: boolean,
  requested?: WireframeUiState,
): WireframeUiState {
  if (!canAdminister) {
    return "forbidden";
  }
  return requested ?? "success";
}

export const resolveAdminMemberState = resolveAdminInviteState;
export const resolveLeagueSeasonState = resolveAdminInviteState;
export const resolveLeagueCalendarState = resolveAdminInviteState;

export function resolveJoinInviteState(
  canJoin: boolean,
  requested?: WireframeUiState,
): WireframeUiState {
  if (!canJoin || requested === "forbidden") {
    return "forbidden";
  }
  return requested ?? "empty";
}
