/**
 * Stato di un calciatore dalle formazioni probabili: stessa regola su web e app.
 *
 * `doubt` (1.5, Rosario 28/11) = assente «in dubbio» per il fornitore (Doubtful, Questionable,
 * Day to day…): può giocare e resta selezionabile. Il server lo segnala con il campo nuovo
 * `probableDoubt`, lasciando `probableHint = "unavailable"` per l'app 1.4 (che lo vede grigio).
 */
export type ProbableTone = "starter" | "bench" | "expelled" | "unavailable" | "doubt";

export type ProbableRow = {
  probableHint?: "starter" | "bench" | "unavailable" | null;
  probableAbsence?: "suspended" | "injured" | "other" | null;
  probableDoubt?: boolean | null;
  selectionBlocked?: boolean;
};

/** «In dubbio»: assenza non certa, nient'altro gli toglie il voto, non è una squalifica. */
export function isProbableDoubt(row: ProbableRow): boolean {
  return (
    row.probableDoubt === true &&
    row.probableHint === "unavailable" &&
    row.selectionBlocked !== true &&
    row.probableAbsence !== "suspended"
  );
}

export function probableToneOf(row: ProbableRow): ProbableTone | null {
  if (isProbableDoubt(row)) return "doubt";
  if (row.probableHint === "unavailable" || row.selectionBlocked) {
    return row.probableAbsence === "suspended" ? "expelled" : "unavailable";
  }
  if (row.probableHint === "starter") return "starter";
  if (row.probableHint === "bench") return "bench";
  return null;
}

/**
 * Alone di un calciatore in campo: lo stato della formazione probabile, oppure `none` quando il
 * dato manca (nessuna formazione probabile per la partita, giocatore non abbinato dal servizio, o
 * né titolare né panchina prevista). Prima chi non aveva il dato restava senza alone e non si
 * capiva perché (Rosario, 27/11): ora ha un alone neutro con la voce «Nessuna informazione».
 */
export type PitchHalo = ProbableTone | "none";

export const NO_INFO_LABEL = "Nessuna informazione";

/** Voce della legenda per l'alone arancione (1.5). */
export const DOUBT_LABEL = "In dubbio";

export function pitchHaloOf(row: ProbableRow): PitchHalo {
  return probableToneOf(row) ?? "none";
}

/** Voci della legenda del campo, nell'ordine mostrato da sito e app. */
export const PITCH_HALO_LEGEND: readonly { halo: PitchHalo; label: string }[] = [
  { halo: "starter", label: "Titolare probabile" },
  { halo: "bench", label: "Possibile panchina" },
  { halo: "expelled", label: "Espulso / squalificato (non selezionabile)" },
  { halo: "unavailable", label: "Indisponibile" },
  { halo: "doubt", label: DOUBT_LABEL },
  { halo: "none", label: NO_INFO_LABEL },
];
