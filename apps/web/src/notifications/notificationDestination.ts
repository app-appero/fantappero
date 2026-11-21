import type { LeagueSummary, NotificationItem } from "@fantappero/contracts";

/** Destinazione di riserva quando il deep link non è arrivato col payload. */
const DESTINATION_BY_TITLE: Record<string, string> = {
  "Nuovo invito a una lega": "/inviti",
  "Scadenza formazione in arrivo": "/formazione",
  "Busta aggiudicata": "/mercato",
  "Busta non aggiudicata": "/mercato",
  "Svincolato aggiudicato": "/svincolati",
  "Svincolato perso": "/svincolati",
  "Spareggio svincolati aperto": "/svincolati",
  "Spareggio svincolati annullato": "/svincolati",
  "Lotto aggiudicato": "/mercato",
  "Sei stato sorpassato": "/mercato",
  "Scelta richiesta: rosa al completo": "/mercato",
  "Asta a rilanci iniziata": "/mercato",
  "Nuova proposta di scambio": "/mercato",
  "Scambio accettato": "/mercato",
  "Scambio in attesa di approvazione": "/mercato",
  "Scambio rifiutato": "/mercato",
  "Controproposta ricevuta": "/mercato",
  "Scambio approvato": "/mercato",
  "Scambio rifiutato dall'amministratore": "/mercato",
  "Aggiornamento scambio": "/mercato",
  "Turno omologato": "/classifica",
  "Correzione al turno omologato": "/classifica",
};

function isInternalPath(value: string): boolean {
  return value.startsWith("/") && !value.startsWith("//") && !value.includes("://");
}

/** Pagina interna aperta dal click sulla notifica. `null` se non c'è una meta. */
export function resolveNotificationDestination(
  item: Pick<NotificationItem, "deepLink" | "title">,
): string | null {
  const link = item.deepLink?.trim() ?? "";
  if (isInternalPath(link)) {
    return link;
  }
  return DESTINATION_BY_TITLE[item.title] ?? null;
}

/**
 * Lega da rendere attiva al click su una notifica: il `?lega=` della destinazione, se è un'altra
 * lega e l'utente ne fa parte; altrimenti `null` (si resta nella lega attiva, come prima).
 *
 * AuthProvider applica `?lega=` una volta per valore (QA 21/11, bb5be76): se l'indirizzo ha già
 * quel valore, per esempio dopo un cambio lega dal selettore sulla pagina aperta da un'altra
 * notifica della stessa lega, il click da solo non la riattiverebbe (Rosario 21/11).
 */
export function notificationLeagueToActivate(
  destination: string,
  session: { activeLeagueId: string | null; leagues: readonly Pick<LeagueSummary, "id">[] },
): string | null {
  if (!isInternalPath(destination)) {
    return null;
  }
  const queryIndex = destination.indexOf("?");
  if (queryIndex === -1) {
    return null;
  }
  const query = destination.slice(queryIndex + 1).split("#")[0] ?? "";
  const leagueId = new URLSearchParams(query).get("lega");
  if (!leagueId || leagueId === session.activeLeagueId) {
    return null;
  }
  return session.leagues.some((league) => league.id === leagueId) ? leagueId : null;
}
