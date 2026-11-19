/** Scheda dell'Asta: buste chiuse (sealed) o rilanci in tempo reale (live). */
export type AuctionMode = "buste" | "live";

/**
 * Scheda richiesta dai parametri di navigazione (es. apertura da una notifica
 * dell'asta a rilanci, vedi notificationDestination.ts), o `undefined` se i
 * parametri non ne indicano una valida: in quel caso resta la scheda corrente.
 */
export function auctionModeFromParams(params: unknown): AuctionMode | undefined {
  if (!params || typeof params !== "object") {
    return undefined;
  }
  const modalita = (params as { modalita?: unknown }).modalita;
  return modalita === "buste" || modalita === "live" ? modalita : undefined;
}
