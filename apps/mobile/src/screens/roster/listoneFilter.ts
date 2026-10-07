import type { FantasyRole, LeagueListoneEntry } from "@fantappero/contracts";

export type RoleTab = "all" | FantasyRole;

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
): LeagueListoneEntry[] {
  const normalized = query.trim().toLocaleLowerCase("it-IT");
  return filterByTab(entries, tab).filter((entry) => {
    if (!normalized) {
      return true;
    }
    const haystack = `${entry.canonicalName} ${entry.clubName ?? ""}`.toLocaleLowerCase("it-IT");
    return haystack.includes(normalized);
  });
}
