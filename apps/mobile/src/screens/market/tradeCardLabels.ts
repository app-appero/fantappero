// Etichette della scheda di una proposta di scambio: le stesse del web
// (MarketPage), che prima sul mobile erano "Offre"/"Chiede" e senza riga di
// scadenza quando la proposta non scade (QA 19/11).

/** Parte della proposta che il proponente cede. */
export const TRADE_OFFERED_LABEL = "Offerti";

/** Parte della proposta che il proponente chiede in cambio. */
export const TRADE_REQUESTED_LABEL = "Richiesti";

/** Riga di scadenza, sempre presente: "Scade il …" oppure "Nessuna scadenza". */
export function tradeExpiryLabel(expiresAt: string | null | undefined): string {
  const value = (expiresAt ?? "").trim();
  if (!value) {
    return "Nessuna scadenza";
  }
  const when = new Date(value).toLocaleString("it-IT", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `Scade il ${when}`;
}
