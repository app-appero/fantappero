/**
 * Foglio che si apre toccando «Campionato» o «Squadra» nella ricerca del listone (Rosa →
 * Inserimento manuale, Rosario 21/11): «Tutti i campionati» o «Tutte le squadre» in cima,
 * poi le voci con i loro calciatori, come nella proposta mostrata a Rosario.
 *
 * Solo logica pura e import di tipo: gira nei test `node:test` senza il bundle di
 * `@fantappero/contracts`. Opzioni, conti e scelte vengono da `listoneFilters.ts` di
 * `@fantappero/contracts`, uguali sul web (dove ci sono i menu nativi).
 */
import type { ListoneFilterOption } from "@fantappero/contracts";

export type ListoneSheetRow = {
  /** `null` per la voce «tutti». */
  value: string | null;
  label: string;
  count: number;
  selected: boolean;
  accessibilityLabel: string;
};

function playersLabel(count: number): string {
  return count === 1 ? "1 calciatore" : `${count} calciatori`;
}

/**
 * Righe del foglio: prima «tutti» (con i calciatori di tutte le voci), poi le voci nell'ordine
 * ricevuto. Una scelta che non è più fra le voci conta come «tutti».
 */
export function listoneSheetRows(
  options: readonly ListoneFilterOption[],
  selectedId: string | null,
  allLabel: string,
): ListoneSheetRow[] {
  const selected = selectedId && options.some((option) => option.id === selectedId) ? selectedId : null;
  const total = options.reduce((sum, option) => sum + option.count, 0);
  return [
    {
      value: null,
      label: allLabel,
      count: total,
      selected: selected === null,
      accessibilityLabel: `${allLabel}, ${playersLabel(total)}`,
    },
    ...options.map((option) => ({
      value: option.id,
      label: option.name,
      count: option.count,
      selected: option.id === selected,
      accessibilityLabel: `${option.name}, ${playersLabel(option.count)}`,
    })),
  ];
}

/** Titolo del foglio: «Squadra · Serie A» con un campionato scelto, se no «Squadra». */
export function listoneSheetTitle(filterLabel: string, competitionName: string | null): string {
  return competitionName ? `${filterLabel} · ${competitionName}` : filterLabel;
}

/** Etichetta per lettori di schermo del menu chiuso: «Squadra: Fiorentina. Tocca per cambiare». */
export function listoneTriggerAccessibilityLabel(filterLabel: string, valueLabel: string): string {
  return `${filterLabel}: ${valueLabel}. Tocca per cambiare`;
}
