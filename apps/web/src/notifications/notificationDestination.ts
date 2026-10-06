import type { NotificationItem } from "@fantappero/contracts";

/** Destinazione di riserva quando il deep link non è arrivato col payload. */
const DESTINATION_BY_TITLE: Record<string, string> = {
  "Nuovo invito a una lega": "/inviti",
  "Scadenza formazione in arrivo": "/formazione",
  "Busta aggiudicata": "/mercato",
  "Busta non aggiudicata": "/mercato",
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
