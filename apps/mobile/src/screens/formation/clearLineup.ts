/**
 * Testi di «Svuota formazione» nella schermata Formazione (Rosario, 20/11): voce nella scheda
 * «•••», conferma (Alert) e messaggio dopo lo svuotamento. La logica è in `benchQuota.ts`
 * (`clearLineupKeepingLocked`).
 *
 * La panchina non può restare vuota (tutta la rosa che non gioca è in panchina o in tribuna): torna
 * all'ordine della rosa, e i testi lo dicono. Stessi testi del web (`CLEAR_LINEUP_*` in
 * `@fantappero/contracts`), tranne il tasto della conferma («Svuota», nell'Alert basta) e il
 * messaggio finale, che nell'app parla dei cerchi del campo e del tasto «Formazione migliore».
 *
 * Solo stringhe: gira nei test `node:test` senza il bundle di `@fantappero/contracts`.
 */
export const CLEAR_LINEUP_TITLE = "Svuota formazione";
export const CLEAR_LINEUP_DESCRIPTION =
  "Toglie i titolari e rimette la panchina nell'ordine della rosa, per ricominciare da capo.";
export const CLEAR_LINEUP_CONFIRM_TITLE = "Svuotare la formazione?";
export const CLEAR_LINEUP_CONFIRM_BODY =
  "Tolgo tutti i titolari e rimetto la panchina nell'ordine della rosa, così la ricomponi da capo.";
export const CLEAR_LINEUP_CONFIRM_POINTS: readonly string[] = [
  "I giocatori già bloccati restano al loro posto.",
  "Finché non salvi, vale ancora la formazione salvata: puoi tornare indietro con «Annulla modifiche».",
  "A turno iniziato, salvare la nuova formazione conta come una mossa.",
];
export const CLEAR_LINEUP_CANCEL_LABEL = "Indietro";
export const CLEAR_LINEUP_CONFIRM_LABEL = "Svuota";

const HELD_NOTE = "In panchina resta al suo posto anche chi è davanti a un giocatore già bloccato.";

/** Il testo dell'Alert: la frase e, sotto, i tre punti. */
export function clearLineupConfirmMessage(): string {
  return [CLEAR_LINEUP_CONFIRM_BODY, "", ...CLEAR_LINEUP_CONFIRM_POINTS.map((point) => `• ${point}`)].join("\n");
}

/** Messaggio dopo lo svuotamento; dice chi resta in panchina solo se succede (turno iniziato). */
export function clearLineupSuccessMessage(heldBenchCount: number): string {
  const base = "Formazione svuotata. Scegli i titolari toccando i cerchi, oppure usa «Formazione migliore».";
  return heldBenchCount > 0 ? `${base} ${HELD_NOTE}` : base;
}
