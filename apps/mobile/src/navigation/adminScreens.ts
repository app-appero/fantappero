import type { OperatorWatchTarget } from "@fantappero/contracts";
import type { AdminStackParamList } from "./types";

/**
 * Voce del menù operatore → schermata dello stack. Usata dal menù (`AdminNavigator`) e dalle
 * righe di «Da guardare» del Riepilogo, che portano alla stessa sezione del menù.
 */
export const ADMIN_SCREEN_BY_ID: Record<string, keyof AdminStackParamList> = {
  "admin-home": "AdminHome",
  "admin-leagues": "AdminLeagues",
  "admin-users": "AdminUsers",
  "admin-listone": "AdminListone",
  "admin-turni": "AdminTurni",
  "admin-jobs": "AdminJobs",
  "admin-notifications": "AdminNotifications",
  "admin-email": "AdminEmail",
  "admin-feedback": "AdminFeedback",
  "admin-app-version": "AdminAppVersion",
};

/** Schermata dello stack → voce del menù da evidenziare. */
export const ADMIN_NAV_ID_BY_ROUTE: Record<string, string> = Object.fromEntries(
  Object.entries(ADMIN_SCREEN_BY_ID).map(([id, screen]) => [screen, id]),
);

/** Schermata a cui porta una riga di «Da guardare». */
export function adminScreenForWatchTarget(
  target: OperatorWatchTarget,
): keyof AdminStackParamList {
  return ADMIN_SCREEN_BY_ID[target] ?? "AdminHome";
}
