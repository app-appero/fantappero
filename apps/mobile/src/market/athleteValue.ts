/**
 * Valore di mercato e media stagionale nelle righe del mercato (1.3, Rosario 21-22/11, canvas
 * «Proposte 1.3», scheda «Valore di mercato»).
 *
 * - Media stagionale: verde con il solo numero se è della stagione in corso («6,45»), rossa
 *   con l'anno se è quella della stagione scorsa («6,12 · 25/26»), niente se manca.
 * - «Valore N»: solo se il backend lo manda (assente da un backend più vecchio o `null` fuori
 *   dal listone).
 * - «Ordina per media» accanto a «Solo disponibili»: ordina con `sortBySeasonAverageDesc` di
 *   `@fantappero/contracts` (passato dal componente); «Azzera filtri» la spegne e lascia
 *   «Solo disponibili» com'è (Rosario, 22/11).
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`.
 */
import type { AthleteMarketFields, AthleteSeasonAverage } from "@fantappero/contracts";

/** Numero con la virgola e `digits` decimali: 6.45 → «6,45». */
export function formatDecimalIt(value: number, digits = 2): string {
  return value.toFixed(digits).replace(".", ",");
}

/** Intero con il punto delle migliaia: 1650 → «1.650». */
export function formatIntegerIt(value: number): string {
  const rounded = Math.round(value);
  const sign = rounded < 0 ? "-" : "";
  return sign + String(Math.abs(rounded)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/** `current`: verde (stagione in corso); `previous`: rossa (stagione scorsa). */
export type SeasonAverageTone = "current" | "previous";

export type SeasonAverageDisplay = {
  /** «6,45» o «6,12 · 25/26». */
  text: string;
  tone: SeasonAverageTone;
  accessibilityLabel: string;
};

/** Segnaposto della media dove la colonna resta (scheda, riepiloghi): «—». */
export const NO_SEASON_AVERAGE = "—";

/** Media da mostrare in una riga del mercato; `null` se non c'è (nessuna etichetta). */
export function seasonAverageDisplay(
  average: AthleteSeasonAverage | null | undefined,
): SeasonAverageDisplay | null {
  if (!average || typeof average.value !== "number" || !Number.isFinite(average.value)) {
    return null;
  }
  const value = formatDecimalIt(average.value);
  if (average.isCurrent) {
    return {
      text: value,
      tone: "current",
      accessibilityLabel: `Media ${value}, stagione in corso`,
    };
  }
  return {
    text: `${value} · ${average.seasonLabel}`,
    tone: "previous",
    accessibilityLabel: `Media ${value}, stagione ${average.seasonLabel}`,
  };
}

/** Testo della media o «—» dove serve sempre un valore. */
export function seasonAverageText(average: AthleteSeasonAverage | null | undefined): string {
  return seasonAverageDisplay(average)?.text ?? NO_SEASON_AVERAGE;
}

/** Valore utilizzabile (intero non negativo) o `null`. */
export function usableMarketValue(value: number | null | undefined): number | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    return null;
  }
  return Math.round(value);
}

/** «Valore 58»; `null` se il Valore manca (l'etichetta non si mostra). */
export function marketValueLabel(value: number | null | undefined): string | null {
  const usable = usableMarketValue(value);
  return usable === null ? null : `Valore ${usable}`;
}

/** Etichette di una riga del mercato: Valore e media, ognuna solo se c'è. */
export type AthleteMarketTagsModel = {
  valueLabel: string | null;
  average: SeasonAverageDisplay | null;
};

export function athleteMarketTags(fields: AthleteMarketFields | null | undefined): AthleteMarketTagsModel {
  return {
    valueLabel: marketValueLabel(fields?.marketValue),
    average: seasonAverageDisplay(fields?.seasonAverage),
  };
}

/** `true` se la riga non ha né Valore né media (niente da mostrare). */
export function isEmptyMarketTags(tags: AthleteMarketTagsModel): boolean {
  return tags.valueLabel === null && tags.average === null;
}

// --- «Ordina per media» -----------------------------------------------------------------------

/** Le due caselle sopra il listone della Rosa. */
export type ListoneViewToggles = {
  onlyFree: boolean;
  sortByAverage: boolean;
};

export const DEFAULT_LISTONE_VIEW_TOGGLES: ListoneViewToggles = {
  onlyFree: false,
  sortByAverage: false,
};

export const SORT_BY_AVERAGE_LABEL = "Ordina per media";

/**
 * Righe già filtrate nell'ordine scelto: con «Ordina per media» accesa le ordina con `sortDesc`
 * (nell'app `sortBySeasonAverageDesc` dei contratti: media più alta prima, chi non l'ha in
 * fondo); spenta, restano nell'ordine del listone.
 */
export function orderListoneRows<T extends AthleteMarketFields>(
  rows: readonly T[],
  sortByAverage: boolean,
  sortDesc: (items: readonly T[]) => T[],
): readonly T[] {
  return sortByAverage ? sortDesc(rows) : rows;
}

/**
 * «Azzera filtri»: spegne «Ordina per media»; «Solo disponibili» resta com'è (Rosario, 22/11).
 */
export function resetListoneViewToggles(toggles: ListoneViewToggles): ListoneViewToggles {
  return { onlyFree: toggles.onlyFree, sortByAverage: false };
}
