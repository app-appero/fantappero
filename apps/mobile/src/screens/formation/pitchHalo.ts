/**
 * Alone dei titolari in campo nella schermata Formazione (Rosario, 27/11).
 *
 * Solo logica pura: gira nei test `node:test` senza il bundle di `@fantappero/contracts`. Stessa
 * regola del sito (`pitchHaloOf` e `PITCH_HALO_LEGEND` in `packages/contracts/src/probableTone.ts`).
 */

/**
 * Stato dalla formazione probabile, come `probableTone` in `FormationParts.tsx`.
 * `doubt` (1.5, Rosario 28/11) = «in dubbio» per il fornitore: arancione e selezionabile.
 */
export type HaloTone = "starter" | "bench" | "expelled" | "unavailable" | "doubt";

/** Campi del server che decidono il tono (stessa regola di `probableToneOf` del sito). */
export type ProbableRow = {
  probableHint?: "starter" | "bench" | "unavailable" | null;
  probableAbsence?: "suspended" | "injured" | "other" | null;
  probableDoubt?: boolean | null;
  selectionBlocked?: boolean;
};

/**
 * «In dubbio»: il server manda `probableDoubt` (campo nuovo, 1.5) lasciando
 * `probableHint = "unavailable"` per l'app 1.4. Mai per un assente certo o squalificato.
 */
export function isProbableDoubt(row: ProbableRow): boolean {
  return (
    row.probableDoubt === true &&
    row.probableHint === "unavailable" &&
    row.selectionBlocked !== true &&
    row.probableAbsence !== "suspended"
  );
}

export function haloToneOf(row: ProbableRow): HaloTone | null {
  if (isProbableDoubt(row)) return "doubt";
  if (row.probableHint === "unavailable" || row.selectionBlocked) {
    return row.probableAbsence === "suspended" ? "expelled" : "unavailable";
  }
  if (row.probableHint === "starter") return "starter";
  if (row.probableHint === "bench") return "bench";
  return null;
}

/**
 * `none` = nessuna informazione: nessuna formazione probabile per la partita, giocatore non
 * abbinato dal servizio, o né titolare né panchina prevista. Prima restava senza alone e non si
 * capiva perché; ora ha un alone neutro con la voce «Nessuna informazione» in legenda.
 */
export type PitchHalo = HaloTone | "none";

export const NO_INFO_LABEL = "Nessuna informazione";

/** Voce della legenda dell'alone arancione, uguale al sito. */
export const DOUBT_LABEL = "In dubbio";

/** Alone di un calciatore schierato; per uno slot vuoto non c'è alone. */
export function pitchHalo(tone: HaloTone | null | undefined): PitchHalo {
  return tone ?? "none";
}

export const HALO_COLOR: Record<PitchHalo, string> = {
  starter: "#22c55e",
  bench: "#facc15",
  expelled: "#ef4444",
  unavailable: "#9ca3af",
  // Stesso arancione del sito (--fa-halo-doubt): ben distinto dal giallo della panchina.
  doubt: "#ea580c",
  none: "#e2e8f0",
};

/** Fondo del nome sotto il pallino «in dubbio»: il bianco sopra arriva a 5,2:1 (come il sito). */
export const DOUBT_LABEL_BG = "#c2410c";

/** Voci della legenda, nell'ordine del sito. */
export const PITCH_HALO_LEGEND: readonly { halo: PitchHalo; label: string }[] = [
  { halo: "starter", label: "Titolare probabile" },
  { halo: "bench", label: "Possibile panchina" },
  { halo: "expelled", label: "Espulso / squalificato (non selezionabile)" },
  { halo: "unavailable", label: "Indisponibile" },
  { halo: "doubt", label: DOUBT_LABEL },
  { halo: "none", label: NO_INFO_LABEL },
];
