import type { WireframeUiState } from "@fantappero/contracts";

export type DirectoryDemoState =
  | WireframeUiState
  | "unavailable"
  | "already-invited"
  | "capacity";

export type DemoCoach = {
  id: string;
  displayName: string;
  userType: "human" | "ai";
  available: boolean;
  alreadyInvited?: boolean;
};

export const DEMO_COACHES: readonly DemoCoach[] = [
  { id: "coach-giulia", displayName: "Giulia Bianchi", userType: "human", available: true },
  {
    id: "coach-luca",
    displayName: "Luca Verdi",
    userType: "human",
    available: true,
    alreadyInvited: true,
  },
  { id: "coach-sara", displayName: "Sara Neri", userType: "human", available: false },
  { id: "coach-ai", displayName: "Allenatore IA 01", userType: "ai", available: true },
];

export function resolveDirectoryState(
  canView: boolean,
  requested?: DirectoryDemoState,
): DirectoryDemoState {
  if (!canView || requested === "forbidden") {
    return "forbidden";
  }
  return requested ?? "success";
}

export function resolveNominalInviteOutcome(
  coach: DemoCoach,
  memberCount: number,
  capacity: number,
): DirectoryDemoState {
  if (memberCount >= capacity) {
    return "capacity";
  }
  if (!coach.available) {
    return "unavailable";
  }
  if (coach.alreadyInvited) {
    return "already-invited";
  }
  return "success";
}

export function resolveReceivedInvitesState(
  canView: boolean,
  requested?: DirectoryDemoState,
): DirectoryDemoState {
  if (!canView || requested === "forbidden") {
    return "forbidden";
  }
  return requested ?? "success";
}
