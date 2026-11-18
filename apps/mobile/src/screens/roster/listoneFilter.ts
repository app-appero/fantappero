import type { FantasyRole, LeagueListoneEntry } from "@fantappero/contracts";

export type RoleTab = "all" | FantasyRole;

// Ricerca senza accenti e senza maiuscole: "dembele" trova "A. Dembélé" (QA 18/11).

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

const COMBINING_MARKS = /[̀-ͯ]/g;
const NON_DECOMPOSING_PATTERN = /[øłđðßæœıþ]/g;

export function foldSearchText(value: string): string {
  const lowered = value.toLocaleLowerCase("it-IT");
  const decomposed = typeof lowered.normalize === "function" ? lowered.normalize("NFD") : lowered;
  return decomposed
    .replace(COMBINING_MARKS, "")
    .replace(NON_DECOMPOSING_PATTERN, (char) => NON_DECOMPOSING[char] ?? char)
    .trim();
}

/** `true` se `haystack` contiene `query`, ignorando accenti e maiuscole. */
export function matchesSearch(haystack: string, query: string): boolean {
  const needle = foldSearchText(query);
  return needle.length === 0 || foldSearchText(haystack).includes(needle);
}

export const ROLE_TABS: Array<{ value: RoleTab; label: string }> = [
  { value: "all", label: "Tutti" },
  { value: "P", label: "Portieri" },
  { value: "D", label: "Difensori" },
  { value: "C", label: "Centrocampisti" },
  { value: "A", label: "Attaccanti" },
];

export const ROSTER_PAGE_SIZE = 10;
export const LISTONE_PAGE_SIZE = 20;

export function filterByTab(entries: LeagueListoneEntry[], tab: RoleTab): LeagueListoneEntry[] {
  if (tab === "all") {
    return entries;
  }
  return entries.filter((entry) => entry.effectiveRole === tab);
}

export function filterListone(
  entries: LeagueListoneEntry[],
  tab: RoleTab,
  query: string,
  onlyFree = false,
  ownedAthleteIds?: ReadonlySet<string>,
): LeagueListoneEntry[] {
  const normalized = foldSearchText(query);
  const hideOwned = onlyFree && normalized.length === 0;
  return filterByTab(entries, tab).filter((entry) => {
    if (hideOwned && ownedAthleteIds?.has(entry.athleteId)) {
      return false;
    }
    if (!normalized) {
      return true;
    }
    const haystack = foldSearchText(`${entry.canonicalName} ${entry.clubName ?? ""}`);
    return haystack.includes(normalized);
  });
}
