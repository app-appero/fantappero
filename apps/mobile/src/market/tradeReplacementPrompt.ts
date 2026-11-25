/**
 * Apertura automatica della finestra «Scegli il sostituto» (1.5): una volta per sessione
 * dell'app, cioè finché l'app resta aperta. Con «Più tardi» non si riapre da sola fino alla
 * sessione dopo (riavvio dell'app); i riquadri in Rosa e Formazione restano e la riaprono, e il
 * link della notifica la apre sempre.
 *
 * Solo logica pura: gira nei test `node:test`. Sul sito lo stesso vale per la sessione del
 * browser (`sessionStorage`, chiave `replacementPromptStorageKey` di `@fantappero/contracts`).
 */

const shownThisSession = new Set<string>();

/** La finestra si è già aperta da sola in questa lega da quando l'app è aperta. */
export function replacementPromptShown(leagueId: string): boolean {
  return shownThisSession.has(leagueId);
}

export function markReplacementPromptShown(leagueId: string): void {
  shownThisSession.add(leagueId);
}

/** Solo per i test: come un riavvio dell'app. */
export function resetReplacementPromptMemory(): void {
  shownThisSession.clear();
}

/** Parametro del link della notifica «Scegli il sostituto dopo lo scambio» (`/rosa?sostituto=1`). */
export const REPLACEMENT_ROUTE_PARAM = "sostituto";

export function wantsReplacementSheet(params: Record<string, unknown> | null | undefined): boolean {
  return params?.[REPLACEMENT_ROUTE_PARAM] === "1";
}
