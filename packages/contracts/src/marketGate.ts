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
 * Gli inviti nominativi in attesa (`pendingInviteCount`) tengono un posto ma non rendono la
 * lega al completo: si mostrano accanto al conto, «3/4 · 1 invito in attesa» (Rosario, 20/11).
 *
 * Sull'app mobile la stessa logica è copiata in `apps/mobile/src/market/marketGateNotice.ts`
 * (i test `node:test` non importano il bundle di `@fantappero/contracts`).
 */
export type MarketGateState = Pick<MarketGate, "marketOpen"> &
  Partial<
    Pick<MarketGate, "memberCount" | "participantCount" | "leagueFull" | "pendingInviteCount">
  >;

/** «1 invito in attesa», «2 inviti in attesa». */
export function pendingInvitesLabel(count: number): string {
  return count === 1 ? "1 invito in attesa" : `${count} inviti in attesa`;
}

/** «3/4», o «3/4 · 1 invito in attesa» quando ci sono inviti nominativi in attesa. */
export function leagueOccupancyLabel(
  memberCount: number,
  participantCount: number | null | undefined,
  pendingInviteCount: number | null | undefined = 0,
): string {
  const total = participantCount ?? "?";
  const pending = pendingInviteCount ?? 0;
  return pending > 0
    ? `${memberCount}/${total} · ${pendingInvitesLabel(pending)}`
    : `${memberCount}/${total}`;
}

/** «Il mercato si apre quando la lega è al completo (3/4 · 1 invito in attesa).» */
export function leagueNotFullMessage(
  memberCount: number,
  participantCount: number | null | undefined,
  pendingInviteCount: number | null | undefined = 0,
): string {
  const occupancy = leagueOccupancyLabel(memberCount, participantCount, pendingInviteCount);
  return `Il mercato si apre quando la lega è al completo (${occupancy}).`;
}

/** Testo da mostrare (interruttore e banner) finché la lega non è al completo, altrimenti `null`. */
export function marketNotFullNotice(gate: MarketGateState | null | undefined): string | null {
  if (!gate || gate.leagueFull !== false) {
    return null;
  }
  return leagueNotFullMessage(gate.memberCount ?? 0, gate.participantCount, gate.pendingInviteCount);
}

/** L'interruttore non si accende a lega incompleta; spegnerlo resta sempre possibile. */
export function marketSwitchLocked(gate: MarketGateState): boolean {
  return gate.leagueFull === false && !gate.marketOpen;
}

/** Rosa, aste e scambi del partecipante: interruttore acceso e lega al completo. */
export function isMarketActive(gate: MarketGateState): boolean {
  return gate.marketOpen && gate.leagueFull !== false;
}
