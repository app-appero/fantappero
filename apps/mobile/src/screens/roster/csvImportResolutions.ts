import type { RosterImportResolution } from "@fantappero/contracts";

/** Scelte per i nomi ambigui dell'import Excel: numero di riga → calciatore scelto. */
export type CsvResolutions = Readonly<Record<number, string>>;

/**
 * Tocco su un candidato di un nome ambiguo: lo sceglie, oppure toglie la scelta
 * se era già quello (QA 19-20/11, omonimi come i due Toni Fernández).
 */
export function toggleCsvResolution(
  resolutions: CsvResolutions,
  rowNumber: number,
  athleteId: string,
): Record<number, string> {
  const next: Record<number, string> = { ...resolutions };
  if (next[rowNumber] === athleteId) {
    delete next[rowNumber];
  } else {
    next[rowNumber] = athleteId;
  }
  return next;
}

/** Le scelte da mandare con la conferma, in ordine di riga. */
export function csvResolutionPayload(resolutions: CsvResolutions): RosterImportResolution[] {
  return Object.entries(resolutions)
    .filter(([, athleteId]) => Boolean(athleteId))
    .map(([rowNumber, athleteId]) => ({ rowNumber: Number(rowNumber), athleteId }))
    .sort((left, right) => left.rowNumber - right.rowNumber);
}
