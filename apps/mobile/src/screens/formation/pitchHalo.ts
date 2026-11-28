/**
 * Alone dei titolari in campo nella schermata Formazione (Rosario, 27/11).
 *
 * Solo logica pura: gira nei test `node:test` senza il bundle di `@fantappero/contracts`. Stessa
 * regola del sito (`pitchHaloOf` e `PITCH_HALO_LEGEND` in `packages/contracts/src/probableTone.ts`).
 */

/** Stato dalla formazione probabile, come `probableTone` in `FormationParts.tsx`. */
export type HaloTone = "starter" | "bench" | "expelled" | "unavailable";

/**
 * `none` = nessuna informazione: nessuna formazione probabile per la partita, giocatore non
 * abbinato dal servizio, o né titolare né panchina prevista. Prima restava senza alone e non si
 * capiva perché; ora ha un alone neutro con la voce «Nessuna informazione» in legenda.
 */
export type PitchHalo = HaloTone | "none";

export const NO_INFO_LABEL = "Nessuna informazione";

/** Alone di un calciatore schierato; per uno slot vuoto non c'è alone. */
export function pitchHalo(tone: HaloTone | null | undefined): PitchHalo {
  return tone ?? "none";
}

export const HALO_COLOR: Record<PitchHalo, string> = {
  starter: "#22c55e",
  bench: "#facc15",
  expelled: "#ef4444",
  unavailable: "#9ca3af",
  none: "#e2e8f0",
};

/** Voci della legenda, nell'ordine del sito. */
export const PITCH_HALO_LEGEND: readonly { halo: PitchHalo; label: string }[] = [
  { halo: "starter", label: "Titolare probabile" },
  { halo: "bench", label: "Possibile panchina" },
  { halo: "expelled", label: "Espulso / squalificato (non selezionabile)" },
  { halo: "unavailable", label: "Indisponibile" },
  { halo: "none", label: NO_INFO_LABEL },
];
