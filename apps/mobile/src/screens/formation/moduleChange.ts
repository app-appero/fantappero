/**
 * Cambio modulo nella schermata Formazione (decisione del 19/11).
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`. Lo stesso criterio è replicato sul web in
 * `apps/web/src/pages/FormationPage.tsx`.
 */

/**
 * Come si arriva alla nuova formazione:
 * - `planned`: formazione completa e calciatori bloccati, i bloccati restano esattamente dove
 *   sono (`planModuleChange`), senza chiamare il server;
 * - `best`: si chiede al server la formazione migliore sul nuovo modulo (stesso criterio del
 *   tasto «Formazione migliore»), con i compatibili mostrati subito in attesa della risposta;
 * - `compatible`: la richiesta non si può fare (offline, turno non modificabile): restano solo
 *   i titolari compatibili (`keepStartersForModule`).
 */
export type ModuleChangeRoute = "planned" | "best" | "compatible";

export function moduleChangeRoute(input: {
  /** Calciatori della rosa con la partita già iniziata. */
  lockedCount: number;
  /** Tutti gli slot del modulo attuale sono occupati. */
  lineupComplete: boolean;
  /** Turno modificabile da questo utente (stessa condizione dei tasti della schermata). */
  editable: boolean;
  /** Sessione, lega e turno disponibili: senza, la richiesta non può partire. */
  hasSession: boolean;
}): ModuleChangeRoute {
  if (input.lockedCount > 0 && input.lineupComplete) {
    return "planned";
  }
  return input.editable && input.hasSession ? "best" : "compatible";
}

export const MODULE_CHANGE_FALLBACK_MESSAGE =
  "Non è stato possibile scegliere i migliori per il nuovo modulo: ho tenuto i giocatori compatibili.";

/**
 * Rifiuti previsti del server: rosa insufficiente (o non ancora validata) e turno non
 * modificabile. Non sono guasti: si tengono i compatibili senza mostrare un errore.
 */
const EXPECTED_REFUSAL_CODES: ReadonlySet<string> = new Set([
  "ai_lineup_incomplete",
  "roster_not_validated",
  "turn_not_open",
  "turn_skipped",
  "turn_modification_closed",
]);

/**
 * Messaggio da mostrare quando la formazione migliore per il nuovo modulo non arriva: per
 * «mancano disponibili» (`ai_lineup_incomplete`) quello del server, che dice quanti disponibili
 * mancano per ruolo (gli indisponibili non entrano titolari, 28/11); `null` per gli altri rifiuti
 * previsti; il messaggio breve per ogni errore vero (rete, server, permessi).
 */
export function moduleChangeFallbackNotice(error: unknown): string | null {
  const code =
    error && typeof error === "object" && "code" in error && typeof error.code === "string"
      ? error.code
      : null;
  if (code === "ai_lineup_incomplete") {
    return error instanceof Error && error.message ? error.message : null;
  }
  if (code && EXPECTED_REFUSAL_CODES.has(code)) {
    return null;
  }
  return MODULE_CHANGE_FALLBACK_MESSAGE;
}
