/**
 * Directory fantallenatori: filtri «Tipologia» e «Reimposta filtri», uguali sul sito e
 * nell'app (release 1.5, allineamento app ↔ sito).
 *
 * Solo logica pura: nessun import a runtime.
 */

/** Tipologia di fantallenatore: manuale (persona) o IA. Come `UserType` del profilo. */
export type CoachTypeFilter = "" | "human" | "ai";

export const COACH_TYPE_FILTER_LABEL = "Tipologia";
export const COACH_RESET_FILTERS_LABEL = "Reimposta filtri";

export const COACH_TYPE_OPTIONS: ReadonlyArray<{ value: CoachTypeFilter; label: string }> = [
  { value: "", label: "Tutte" },
  { value: "human", label: "Manuale" },
  { value: "ai", label: "IA" },
];

export interface CoachDirectoryFilters {
  query: string;
  userType: CoachTypeFilter;
  onlyAvailable: boolean;
}

export const NO_COACH_FILTERS: CoachDirectoryFilters = {
  query: "",
  userType: "",
  onlyAvailable: false,
};

/** C'è un filtro attivo: compare «Reimposta filtri». */
export function hasCoachFilters(filters: CoachDirectoryFilters): boolean {
  return filters.query !== "" || filters.userType !== "" || filters.onlyAvailable;
}
