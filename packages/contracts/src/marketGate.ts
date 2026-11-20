import type { MarketGate } from "./market.js";

/**
 * Mercato e lega al completo (decisione di Rosario del 20/11).
 *
 * Il mercato si apre solo quando la lega è al completo (iscritti = partecipanti previsti):
 * fino ad allora l'interruttore «Mercato aperto» non si accende e rosa, aste e scambi del
 * partecipante restano fermi. Le operazioni dell'amministratore sulle rose (assegnazioni,
 * rettifiche, svincoli, import) non dipendono né dalla lega al completo né
 * dall'interruttore: si fermano solo a turno in corso. Una risposta senza `leagueFull`
 * (backend più vecchio, demo) conta come lega al completo: non blocca nulla che prima
 * funzionava.
 *
 * Sull'app mobile la stessa logica è copiata in `apps/mobile/src/market/marketGateNotice.ts`
 * (i test `node:test` non importano il bundle di `@fantappero/contracts`).
 */
export type MarketGateState = Pick<MarketGate, "marketOpen"> &
  Partial<Pick<MarketGate, "memberCount" | "participantCount" | "leagueFull">>;

/** «Il mercato si apre quando la lega è al completo (5/8).» */
export function leagueNotFullMessage(
  memberCount: number,
  participantCount: number | null | undefined,
): string {
  const total = participantCount ?? "?";
  return `Il mercato si apre quando la lega è al completo (${memberCount}/${total}).`;
}

/** Testo da mostrare (interruttore e banner) finché la lega non è al completo, altrimenti `null`. */
export function marketNotFullNotice(gate: MarketGateState | null | undefined): string | null {
  if (!gate || gate.leagueFull !== false) {
    return null;
  }
  return leagueNotFullMessage(gate.memberCount ?? 0, gate.participantCount);
}

/** L'interruttore non si accende a lega incompleta; spegnerlo resta sempre possibile. */
export function marketSwitchLocked(gate: MarketGateState): boolean {
  return gate.leagueFull === false && !gate.marketOpen;
}

/** Rosa, aste e scambi del partecipante: interruttore acceso e lega al completo. */
export function isMarketActive(gate: MarketGateState): boolean {
  return gate.marketOpen && gate.leagueFull !== false;
}
