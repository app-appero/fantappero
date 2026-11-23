/**
 * Pannello operatore → Listone → «Dettaglio del Valore» (1.4): ricerca del calciatore nel
 * listone già caricato dalla schermata e budget della lega. Le frasi e i numeri del dettaglio
 * vengono da `@fantappero/contracts` (`marketValueDetail.ts`), uguali al sito.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test`. La normalizzazione del testo
 * (senza accenti né maiuscole) arriva da fuori: in app è `foldSearchText` del listone.
 */
import type { AdminListoneEntry } from "@fantappero/contracts";

/** Quanti calciatori proporre sotto la ricerca. */
export const VALUE_DETAIL_MAX_RESULTS = 8;
/** Lettere minime prima di cercare. */
export const VALUE_DETAIL_MIN_QUERY = 2;

/** Calciatori del listone che corrispondono a nome o club. */
export function valueDetailCandidates(
  entries: readonly AdminListoneEntry[],
  query: string,
  fold: (text: string) => string,
  max: number = VALUE_DETAIL_MAX_RESULTS,
): AdminListoneEntry[] {
  const normalized = fold(query.trim());
  if (normalized.length < VALUE_DETAIL_MIN_QUERY) {
    return [];
  }
  const found: AdminListoneEntry[] = [];
  for (const entry of entries) {
    if (fold(`${entry.canonicalName} ${entry.clubName ?? ""}`).includes(normalized)) {
      found.push(entry);
      if (found.length >= max) {
        break;
      }
    }
  }
  return found;
}

/** Budget scritto dall'operatore: intero fra 1 e 100.000, altrimenti `null`. */
export function parseValueDetailBudget(text: string): number | null {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }
  const value = Number(trimmed);
  return Number.isInteger(value) && value >= 1 && value <= 100_000 ? value : null;
}
