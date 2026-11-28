/**
 * Apertura della finestra «Scegli il sostituto» (1.5): una volta per sessione dell'app quando si
 * apre da sola, cioè finché l'app resta aperta. Con «Più tardi» non si riapre da sola fino alla
 * sessione dopo (riavvio dell'app); i riquadri in Rosa e Formazione restano e la riaprono, e il
 * link della notifica la apre sempre.
 *
 * Il foglio non deve mai aprirsi due volte per lo stesso motivo (anomalia di Rosario, 24/11: con
 * la notifica di un'altra lega si apriva due volte e «Più tardi» andava toccato due volte). Le
 * cause erano due, quasi insieme: l'apertura da sola al cambio lega e la richiesta della
 * schermata Rosa (`refresh({ openIfPending: true })`). Se la più veloce apriva il foglio e
 * l'utente lo chiudeva, l'altra lo riapriva. Ora ogni apertura passa da qui:
 *
 * - l'apertura da sola (`claimAutoOpen`) vale una volta per lega e per sessione, e la richiesta
 *   esplicita segna anch'essa la lega come già mostrata, così dopo «Più tardi» la prima non
 *   riapre;
 * - la richiesta esplicita (`beginExplicitOpen` → `claimExplicitOpen`) si rinuncia da sola se
 *   nel frattempo il foglio si è già aperto per quella lega: quell'apertura la soddisfa.
 *
 * Solo logica pura: gira nei test `node:test`. Sul sito lo stesso vale per la sessione del
 * browser (`sessionStorage`, chiave `replacementPromptStorageKey` di `@fantappero/contracts`).
 */

/** Dopo un'apertura, una richiesta esplicita arrivata subito dopo per la stessa lega non riapre. */
export const REOPEN_GRACE_MS = 4000;

const shownThisSession = new Set<string>();
const lastOpenedAt = new Map<string, number>();
let openSequence = 0;

/** La finestra si è già aperta in questa lega da quando l'app è aperta (da sola o su richiesta). */
export function replacementPromptShown(leagueId: string): boolean {
  return shownThisSession.has(leagueId);
}

export function markReplacementPromptShown(leagueId: string): void {
  shownThisSession.add(leagueId);
}

function recordOpening(leagueId: string, now: number): void {
  shownThisSession.add(leagueId);
  lastOpenedAt.set(leagueId, now);
  openSequence += 1;
}

/**
 * Apertura da sola (cambio lega, avvio): sì solo la prima volta per lega in questa sessione.
 * Chi riceve `true` apre il foglio; chiamata di nuovo per la stessa lega dà `false`.
 */
export function claimAutoOpen(leagueId: string, now: number = Date.now()): boolean {
  if (shownThisSession.has(leagueId)) {
    return false;
  }
  recordOpening(leagueId, now);
  return true;
}

/** Chi chiede di aprire il foglio (link della notifica, scambio accettato) prende un numero. */
export function beginExplicitOpen(): number {
  return openSequence;
}

/**
 * Risposta alla richiesta esplicita: apre solo se il foglio non si è aperto, per nessuna causa,
 * da quando la richiesta è partita (`token`), né da pochi secondi per questa lega. Altrimenti la
 * richiesta è già soddisfatta e riaprire farebbe comparire il foglio due volte.
 */
export function claimExplicitOpen(
  leagueId: string,
  token: number,
  now: number = Date.now(),
): boolean {
  if (token !== openSequence) {
    return false;
  }
  const last = lastOpenedAt.get(leagueId);
  if (last !== undefined && now - last < REOPEN_GRACE_MS) {
    return false;
  }
  recordOpening(leagueId, now);
  return true;
}

/** Solo per i test: come un riavvio dell'app. */
export function resetReplacementPromptMemory(): void {
  shownThisSession.clear();
  lastOpenedAt.clear();
  openSequence = 0;
}

/** Parametro del link della notifica «Scegli il sostituto dopo lo scambio» (`/rosa?sostituto=1`). */
export const REPLACEMENT_ROUTE_PARAM = "sostituto";

export function wantsReplacementSheet(params: Record<string, unknown> | null | undefined): boolean {
  return params?.[REPLACEMENT_ROUTE_PARAM] === "1";
}
