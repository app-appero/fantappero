/**
 * Filtri della ricerca nel listone della Rosa («Inserimento manuale»): «Campionato» e
 * «Squadra» accanto a testo, ruolo e «Solo disponibili». Li ha chiesti un tester («filtri
 * per campionato, squadra e ruolo»), Rosario li ha approvati il 21/11 per pilota-1.2.
 *
 * Una sola logica per web e app, così i due si comportano allo stesso modo. Solo logica pura
 * e import di tipo: i test `node:test` (anche quelli dell'app) caricano il file dal sorgente.
 *
 * Il campionato arriva dal server (`competitionId`/`competitionName` di ogni voce). Un
 * backend più vecchio non lo manda: allora il filtro «Campionato» non compare e «Squadra»
 * elenca tutti i club, come con un listone di un campionato solo.
 */
import type { FantasyRole, LeagueListoneEntry } from "./leagues.js";

export type ListoneRoleFilter = "all" | FantasyRole;

/** Campi della voce del listone usati dai filtri. */
export type ListoneFilterEntry = Pick<
  LeagueListoneEntry,
  "athleteId" | "canonicalName" | "effectiveRole" | "clubId" | "clubName" | "competitionId" | "competitionName"
>;

/** Campionato e squadra scelti: `null` vuol dire «tutti». */
export interface ListonePlaceFilters {
  competitionId: string | null;
  clubId: string | null;
}

export const NO_LISTONE_PLACE_FILTERS: ListonePlaceFilters = Object.freeze({
  competitionId: null,
  clubId: null,
});

/** Tutti i filtri della ricerca nel listone. */
export interface ListoneFilters extends ListonePlaceFilters {
  role: ListoneRoleFilter;
  query: string;
  onlyFree: boolean;
}

/** Una voce dei menu «Campionato» e «Squadra», con quanti calciatori ha nel listone. */
export interface ListoneFilterOption {
  id: string;
  name: string;
  count: number;
}

export type ListoneFilterKind = "competition" | "club";

export const LISTONE_FILTER_LABEL: Record<ListoneFilterKind, string> = {
  competition: "Campionato",
  club: "Squadra",
};

/** Voce «tutti» in cima a ogni menu, ed etichetta del menu senza scelta. */
export const LISTONE_FILTER_ALL_LABEL: Record<ListoneFilterKind, string> = {
  competition: "Tutti i campionati",
  club: "Tutte le squadre",
};

export const LISTONE_RESET_FILTERS_LABEL = "Azzera filtri";

const COMBINING_MARKS = /[̀-ͯ]/g;
// Lettere che la scomposizione Unicode (NFD) non separa dall'accento.
const NON_DECOMPOSING: Record<string, string> = {
  ø: "o",
  ł: "l",
  đ: "d",
  ð: "d",
  ß: "ss",
  æ: "ae",
  œ: "oe",
  ı: "i",
  þ: "th",
};
const NON_DECOMPOSING_PATTERN = /[øłđðßæœıþ]/g;

/**
 * Chiave di ordinamento senza accenti e maiuscole: «Élan» sta fra le E e non dopo la Z,
 * «Atlético» accanto ad «Athletic». Non usa `Intl.Collator`, che su Hermes (app) e nei
 * browser può ordinare in modo diverso: la stessa chiave dà lo stesso ordine ovunque.
 */
export function listoneNameSortKey(value: string): string {
  const lowered = value.toLocaleLowerCase("it-IT");
  const decomposed = typeof lowered.normalize === "function" ? lowered.normalize("NFD") : lowered;
  return decomposed
    .replace(COMBINING_MARKS, "")
    .replace(NON_DECOMPOSING_PATTERN, (char) => NON_DECOMPOSING[char] ?? char)
    .trim();
}

/** Confronto alfabetico senza accenti e maiuscole; a parità, il testo originale decide. */
export function compareListoneNames(left: string, right: string): number {
  const leftKey = listoneNameSortKey(left);
  const rightKey = listoneNameSortKey(right);
  if (leftKey !== rightKey) {
    return leftKey < rightKey ? -1 : 1;
  }
  return left < right ? -1 : left > right ? 1 : 0;
}

function sortOptions(options: Iterable<ListoneFilterOption>): ListoneFilterOption[] {
  return [...options].sort(
    (left, right) =>
      compareListoneNames(left.name, right.name) || (left.id < right.id ? -1 : left.id > right.id ? 1 : 0),
  );
}

function countOption(
  options: Map<string, ListoneFilterOption>,
  id: string,
  name: string | null | undefined,
): void {
  const current = options.get(id);
  if (current) {
    current.count += 1;
    return;
  }
  options.set(id, { id, name: name?.trim() || "—", count: 1 });
}

/** Campionati presenti nel listone, in ordine alfabetico, con quanti calciatori hanno. */
export function listoneCompetitionOptions(entries: readonly ListoneFilterEntry[]): ListoneFilterOption[] {
  const options = new Map<string, ListoneFilterOption>();
  for (const entry of entries) {
    if (entry.competitionId) {
      countOption(options, entry.competitionId, entry.competitionName);
    }
  }
  return sortOptions(options.values());
}

/**
 * Club del campionato scelto (tutti con `null`), in ordine alfabetico, ciascuno con i suoi
 * calciatori nel listone. Il conto è sul listone intero, non cambia con ruolo o ricerca.
 */
export function listoneClubOptions(
  entries: readonly ListoneFilterEntry[],
  competitionId: string | null,
): ListoneFilterOption[] {
  const options = new Map<string, ListoneFilterOption>();
  for (const entry of entries) {
    if (!entry.clubId) {
      continue;
    }
    if (competitionId && entry.competitionId !== competitionId) {
      continue;
    }
    countOption(options, entry.clubId, entry.clubName);
  }
  return sortOptions(options.values());
}

/** Quali menu mostrare. */
export interface ListoneFilterVisibility {
  /** Solo con due campionati o più: con uno solo il menu non sceglierebbe nulla. */
  competition: boolean;
  /** Appena il listone ha un club. */
  club: boolean;
}

export function listoneFilterVisibility(entries: readonly ListoneFilterEntry[]): ListoneFilterVisibility {
  const competitions = new Set<string>();
  let hasClub = false;
  for (const entry of entries) {
    if (entry.competitionId) {
      competitions.add(entry.competitionId);
    }
    if (entry.clubId) {
      hasClub = true;
    }
  }
  return { competition: competitions.size > 1, club: hasClub };
}

/**
 * Riporta la scelta a valori che il listone ha: un campionato nascosto o sparito torna
 * «tutti», una squadra fuori dal campionato scelto (o sparita) torna «tutte».
 */
export function normalizeListonePlaceFilters(
  entries: readonly ListoneFilterEntry[],
  place: ListonePlaceFilters,
): ListonePlaceFilters {
  let { competitionId, clubId } = place;
  if (
    competitionId &&
    (!listoneFilterVisibility(entries).competition ||
      !listoneCompetitionOptions(entries).some((option) => option.id === competitionId))
  ) {
    competitionId = null;
  }
  if (clubId && !listoneClubOptions(entries, competitionId).some((option) => option.id === clubId)) {
    clubId = null;
  }
  if (competitionId === place.competitionId && clubId === place.clubId) {
    return place;
  }
  return { competitionId, clubId };
}

/** Sceglie il campionato: la squadra resta solo se gioca in quel campionato. */
export function selectListoneCompetition(
  entries: readonly ListoneFilterEntry[],
  place: ListonePlaceFilters,
  competitionId: string | null,
): ListonePlaceFilters {
  return normalizeListonePlaceFilters(entries, { competitionId, clubId: place.clubId });
}

/** Sceglie la squadra fra quelle del campionato scelto. */
export function selectListoneClub(
  entries: readonly ListoneFilterEntry[],
  place: ListonePlaceFilters,
  clubId: string | null,
): ListonePlaceFilters {
  return normalizeListonePlaceFilters(entries, { competitionId: place.competitionId, clubId });
}

export function hasListonePlaceFilters(place: ListonePlaceFilters): boolean {
  return Boolean(place.competitionId || place.clubId);
}

/** Etichetta piccola di un filtro attivo, che si toglie da sola. */
export interface ListoneFilterChip {
  kind: ListoneFilterKind;
  label: string;
  /** Per lettori di schermo e `aria-label`: «Togli il filtro Campionato: Serie A». */
  removeLabel: string;
}

/** I filtri attivi, campionato prima della squadra. Vuoto senza filtri. */
export function listoneFilterChips(
  entries: readonly ListoneFilterEntry[],
  place: ListonePlaceFilters,
): ListoneFilterChip[] {
  const chips: ListoneFilterChip[] = [];
  const add = (kind: ListoneFilterKind, label: string | undefined) => {
    if (label) {
      chips.push({ kind, label, removeLabel: `Togli il filtro ${LISTONE_FILTER_LABEL[kind]}: ${label}` });
    }
  };
  if (place.competitionId) {
    add(
      "competition",
      listoneCompetitionOptions(entries).find((option) => option.id === place.competitionId)?.name,
    );
  }
  if (place.clubId) {
    add(
      "club",
      listoneClubOptions(entries, place.competitionId).find((option) => option.id === place.clubId)?.name,
    );
  }
  return chips;
}

/** Toglie un filtro. Senza campionato la squadra scelta resta valida (sono tutte). */
export function removeListoneFilter(place: ListonePlaceFilters, kind: ListoneFilterKind): ListonePlaceFilters {
  return kind === "competition"
    ? { competitionId: null, clubId: place.clubId }
    : { competitionId: place.competitionId, clubId: null };
}

export interface ListoneFilterOptions {
  /**
   * Come si confronta il testo della ricerca: passare il `foldSearchText` della piattaforma
   * (web `utils/searchText.ts`, app `screens/roster/listoneFilter.ts`), che toglie accenti e
   * maiuscole e ripara la codifica rovinata, come in ogni altra ricerca dell'app.
   */
  fold: (value: string) => string;
  /** Calciatori già in una rosa, nascosti da «Solo disponibili». */
  ownedAthleteIds?: ReadonlySet<string>;
}

/**
 * Il listone filtrato da tutti i filtri insieme: ruolo, campionato, squadra, testo (nome o
 * club) e «Solo disponibili». Come prima, con una ricerca scritta «Solo disponibili» non
 * nasconde i calciatori in rosa: chi cerca un nome lo trova anche per toglierlo.
 */
export function filterListoneEntries<T extends ListoneFilterEntry>(
  entries: readonly T[],
  filters: ListoneFilters,
  options: ListoneFilterOptions,
): T[] {
  const needle = options.fold(filters.query);
  const hideOwned = filters.onlyFree && needle.length === 0;
  return entries.filter((entry) => {
    if (filters.role !== "all" && entry.effectiveRole !== filters.role) {
      return false;
    }
    if (filters.competitionId && entry.competitionId !== filters.competitionId) {
      return false;
    }
    if (filters.clubId && entry.clubId !== filters.clubId) {
      return false;
    }
    if (hideOwned && options.ownedAthleteIds?.has(entry.athleteId)) {
      return false;
    }
    return !needle || options.fold(`${entry.canonicalName} ${entry.clubName ?? ""}`).includes(needle);
  });
}

/** «1 calciatore», «28 calciatori». */
export function listonePlayerCountLabel(count: number): string {
  return count === 1 ? "1 calciatore" : `${count} calciatori`;
}

/** Voce di menu con il conto: «Fiorentina (28)». */
export function listoneOptionLabel(option: ListoneFilterOption): string {
  return `${option.name} (${option.count})`;
}

/** Per lettori di schermo: «Fiorentina, 28 calciatori». */
export function listoneOptionAccessibilityLabel(option: ListoneFilterOption): string {
  return `${option.name}, ${listonePlayerCountLabel(option.count)}`;
}
