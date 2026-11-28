/**
 * Contatore dei titolari («0/11») in Formazione (1.5, Rosario 27/11).
 *
 * Il numero non aveva un colore suo: nel tema scuro usciva col nero di sistema sul fondo
 * scuro e non si leggeva. Ora sotto la soglia (non tutti i titolari scelti) prende il colore
 * del testo del tema (bianco nello scuro, blu notte nel chiaro); a formazione completa resta
 * verde. Solo logica pura: i token sono nomi dei colori del tema, risolti dalla schermata.
 */

export type StartersCounterTone = "complete" | "incomplete";

/** Completo quando i titolari scelti raggiungono gli slot del modulo (di norma 11). */
export function startersCounterTone(filled: number, total: number): StartersCounterTone {
  return filled >= total ? "complete" : "incomplete";
}

/** Colore del tema per ogni stato del contatore: `foreground` è il testo normale del tema. */
export const STARTERS_COUNTER_COLOR_TOKEN = {
  complete: "success",
  incomplete: "foreground",
} as const satisfies Record<StartersCounterTone, "success" | "foreground">;
