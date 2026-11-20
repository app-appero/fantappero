/**
 * Mercato e lega al completo (decisione di Rosario del 20/11).
 *
 * Il mercato si apre solo quando la lega è al completo (iscritti = partecipanti previsti):
 * fino ad allora l'interruttore «Mercato aperto» non si accende e rosa, aste e scambi del
 * partecipante restano fermi. Le operazioni dell'amministratore sulle rose seguono solo
 * l'interruttore. Una risposta senza `leagueFull` (backend più vecchio) conta come lega al
 * completo: non blocca nulla che prima funzionava.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`. Sul web la stessa logica è in `@fantappero/contracts`
 * (`packages/contracts/src/marketGate.ts`).
 */
import type { MarketGate } from "@fantappero/contracts";

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
