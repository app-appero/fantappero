/**
 * Asta live → «Offerta personalizzata» (release 1.5, allineamento app ↔ sito): oltre a
 * «+1», «+5» e «+10» chi partecipa scrive l'importo del rilancio. Stessa regola sul sito e
 * nell'app. Il server resta l'autorità: rifiuta gli importi sotto il minimo.
 *
 * Solo logica pura: nessun import a runtime.
 */

/** L'importo scritto nel campo, se è un numero positivo; altrimenti `null` (campo vuoto o non valido). */
export function customRaiseAmount(text: string): number | null {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  const amount = Number(trimmed);
  return Number.isFinite(amount) && amount > 0 ? amount : null;
}

/** Cosa rilancia il pulsante principale: l'offerta personalizzata se valida, altrimenti il minimo. */
export function raiseTargetAmount(customText: string, minimumNextBid: number | null): number | null {
  return customRaiseAmount(customText) ?? minimumNextBid;
}

/** «Rilancia a 25» con il campo compilato, «Rilancia a <minimo>» (o «—») altrimenti. */
export function raiseButtonLabel(customText: string, minimumNextBid: number | null): string {
  const custom = customText.trim();
  return custom ? `Rilancia a ${custom}` : `Rilancia a ${minimumNextBid ?? "—"}`;
}

/** Segnaposto del campo: «Es. 15» con qualche credito sopra il minimo. */
export function customRaisePlaceholder(minimumNextBid: number | null): string {
  return minimumNextBid !== null ? `Es. ${minimumNextBid + 5}` : "";
}

export const CUSTOM_RAISE_LABEL = "Offerta personalizzata";
