/**
 * Nomi per l'accessibilità di ciò che si chiama «Notifiche».
 *
 * La scheda «Notifiche» del Profilo e il campanello in alto avevano lo stesso nome («Notifiche»):
 * con il lettore di schermo (e nei flussi Maestro per testo) non si distinguevano (corsa M4,
 * 22/11). Il campanello apre l'elenco delle notifiche e resta «Notifiche»; la scheda del Profilo
 * apre le preferenze e si chiama «Impostazioni notifiche». Il testo visibile non cambia e l'id
 * `profile-tabs-notifiche` dei flussi Maestro resta lo stesso.
 *
 * Solo logica pura: gira nei test `node:test`.
 */

/** Campanello dell'intestazione: «Notifiche», o «Notifiche: 3 non lette». */
export function notificationsBellLabel(unread: number): string {
  return unread > 0 ? `Notifiche: ${unread} non lette` : "Notifiche";
}

/** Scheda «Notifiche» del Profilo (preferenze email, push, silenzio). */
export const PROFILE_NOTIFICATIONS_TAB_A11Y_LABEL = "Impostazioni notifiche";

/** Schede del Profilo; l'id fa da suffisso del testID (`profile-tabs-notifiche`). */
export const PROFILE_TABS = [
  { id: "utente", label: "Utente" },
  { id: "notifiche", label: "Notifiche", accessibilityLabel: PROFILE_NOTIFICATIONS_TAB_A11Y_LABEL },
] as const;
