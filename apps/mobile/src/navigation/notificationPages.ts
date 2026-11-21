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

/** Tutte le pagine sono state caricate (con zero notifiche `totalPages` vale 0). */
export function allNotificationPagesLoaded(page: number, totalPages: number): boolean {
  return page >= totalPages;
}

/**
 * Numero accanto a un filtro del centro notifiche, o stringa vuota se non c'è niente da
 * contare. Prima contava solo le notifiche già caricate (30 alla volta) e sembrava il totale
 * (QA 20-21/11). «Tutte» passa `total` dell'API, il conto vero di tutte le notifiche. Per i
 * gruppi (Giocatori, Scambi, …) l'API non dà conteggi, e non potrebbe: si ricavano dal titolo
 * e non coincidono con le categorie del server. Si contano allora sulle pagine caricate e,
 * finché ne mancano, il numero è un minimo: «12+».
 */
export function notificationFilterCountLabel({
  loaded,
  total,
  allLoaded,
}: {
  /** Notifiche del filtro tra quelle già caricate. */
  loaded: number;
  /** Totale dell'API, solo per «Tutte». */
  total?: number | null;
  allLoaded: boolean;
}): string {
  if (total != null) {
    const count = Math.max(total, loaded);
    return count > 0 ? String(count) : "";
  }
  if (loaded <= 0) {
    return "";
  }
  return allLoaded ? String(loaded) : `${loaded}+`;
}
