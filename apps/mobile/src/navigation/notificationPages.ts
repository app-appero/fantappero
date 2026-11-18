import type { NotificationItem } from "@fantappero/contracts";

export const NOTIFICATIONS_PAGE_SIZE = 30;

/**
 * Aggiunge in coda una pagina di notifiche più vecchie, senza doppioni: se nel
 * frattempo ne arrivano di nuove, la pagina successiva può ripeterne qualcuna.
 */
export function appendNotificationPage(
  current: NotificationItem[],
  next: NotificationItem[],
): NotificationItem[] {
  const seen = new Set(current.map((row) => row.id));
  return [...current, ...next.filter((row) => !seen.has(row.id))];
}
