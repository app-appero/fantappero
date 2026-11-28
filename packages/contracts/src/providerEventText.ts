/**
 * Eventi VAR del fornitore in italiano, per lo schermo «Partita» (QA 28/11, N6).
 *
 * Il dettaglio dell'evento VAR arriva dal fornitore dei dati in inglese («Goal cancelled»,
 * «Goal Disallowed - offside»…) e finiva così nella cronologia: «VAR — Goal cancelled». Qui sta
 * l'UNICA funzione che lo traduce, per sito e app: il server continua a mandare il testo
 * originale (l'app già installata lo legge com'è) e ogni schermata lo passa da qui.
 *
 * Solo logica pura. Un testo che non si riconosce resta com'è: meglio l'originale di un testo
 * inventato.
 */

/** Dettaglio assente: la riga dice comunque che c'è stata una revisione. */
const VAR_REVIEW_FALLBACK = "Revisione";

/**
 * Confronto in minuscolo, con trattini e spazi doppi ridotti a uno spazio:
 * «Goal Disallowed - offside» e «goal-disallowed – offside» sono la stessa frase.
 */
const VAR_EVENTS: Record<string, string> = {
  "goal cancelled": "Gol annullato",
  "goal canceled": "Gol annullato",
  "goal disallowed": "Gol annullato",
  "goal disallowed offside": "Gol annullato · fuorigioco",
  "goal disallowed handball": "Gol annullato · fallo di mano",
  "goal confirmed": "Gol confermato",
  "penalty confirmed": "Rigore confermato",
  "penalty cancelled": "Rigore annullato",
  "penalty canceled": "Rigore annullato",
  "card upgrade": "Cartellino cambiato",
  "red card cancelled": "Rosso annullato",
  "red card canceled": "Rosso annullato",
};

function normalizeVarDetail(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[_\-–—]+/g, " ")
    .replace(/\s+/g, " ")
    .replace(/[.!]+$/, "");
}

/**
 * Il dettaglio di un evento VAR in italiano: «Goal cancelled» → «Gol annullato».
 * Senza dettaglio (`null`, vuoto) dice «Revisione»; un testo non riconosciuto resta com'è.
 */
export function italianVarEventText(detail: string | null | undefined): string {
  if (detail == null || detail.trim() === "") {
    return VAR_REVIEW_FALLBACK;
  }
  return VAR_EVENTS[normalizeVarDetail(detail)] ?? detail;
}
