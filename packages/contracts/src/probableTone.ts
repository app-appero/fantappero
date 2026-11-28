/** Stato di un calciatore dalle formazioni probabili: stessa regola su web e app. */
export type ProbableTone = "starter" | "bench" | "expelled" | "unavailable";

export function probableToneOf(row: {
  probableHint?: "starter" | "bench" | "unavailable" | null;
  probableAbsence?: "suspended" | "injured" | "other" | null;
  selectionBlocked?: boolean;
}): ProbableTone | null {
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

export function pitchHaloOf(row: Parameters<typeof probableToneOf>[0]): PitchHalo {
  return probableToneOf(row) ?? "none";
}

/** Voci della legenda del campo, nell'ordine mostrato da sito e app. */
export const PITCH_HALO_LEGEND: readonly { halo: PitchHalo; label: string }[] = [
  { halo: "starter", label: "Titolare probabile" },
  { halo: "bench", label: "Possibile panchina" },
  { halo: "expelled", label: "Espulso / squalificato (non selezionabile)" },
  { halo: "unavailable", label: "Indisponibile" },
  { halo: "none", label: NO_INFO_LABEL },
];
