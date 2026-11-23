/**
 * Scheda «Campionati» della Home lega: i nomi dei campionati, uno per riga e senza taglio.
 * Su una riga sola con `numberOfLines={1}` l'elenco finiva in «La Liga · Premier Leagu…»
 * (QA notte 21→22/11).
 *
 * Solo logica pura e import di tipo: gira nei test `node:test`.
 */
import type { CompetitionSummary } from "@fantappero/contracts";

export function leagueHomeCompetitionsHint(competitions: readonly Pick<CompetitionSummary, "name">[]): string {
  const names = competitions.map((row) => row.name.trim()).filter(Boolean);
  return names.length > 0 ? names.join("\n") : "—";
}

/**
 * Righe massime del suggerimento sotto il numero di una scheda: `undefined` = tutte.
 * Le altre schede (Partecipanti, Crediti, Rosa) restano su una riga.
 */
export function leagueHomeStatHintLines(label: string): number | undefined {
  return label === "Campionati" ? undefined : 1;
}
