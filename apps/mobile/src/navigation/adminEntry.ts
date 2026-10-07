import type { AdminStackParamList } from "./types";

let pendingAdminScreen: keyof AdminStackParamList | null = null;

/** Schermata da aprire al prossimo focus del pannello operazioni. */
export function openAdminScreen(screen: keyof AdminStackParamList): void {
  pendingAdminScreen = screen;
}

export function consumePendingAdminScreen(): keyof AdminStackParamList | null {
  const screen = pendingAdminScreen;
  pendingAdminScreen = null;
  return screen;
}
