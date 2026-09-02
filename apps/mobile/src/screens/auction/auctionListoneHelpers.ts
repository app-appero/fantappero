import type { FantasyRole, LeagueListoneEntry } from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";

const { colors } = theme;

export type RoleTab = "all" | FantasyRole;

export const ROLE_TABS: Array<{ value: RoleTab; label: string }> = [
  { value: "all", label: "Tutti" },
  { value: "P", label: "Portieri" },
  { value: "D", label: "Difensori" },
  { value: "C", label: "Centrocampisti" },
  { value: "A", label: "Attaccanti" },
];

export const ROLE_LABEL: Record<FantasyRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

export function roleBadgeColors(role: FantasyRole): { backgroundColor: string; color: string } {
  if (role === "P") {
    return { backgroundColor: colors.success, color: colors.accentContrast };
  }
  if (role === "D") {
    return { backgroundColor: colors.warning, color: colors.background };
  }
  if (role === "C") {
    return { backgroundColor: colors.accent, color: colors.accentContrast };
  }
  return { backgroundColor: colors.danger, color: colors.accentContrast };
}

export function filterByTab(entries: LeagueListoneEntry[], tab: RoleTab): LeagueListoneEntry[] {
  if (tab === "all") {
    return entries;
  }
  return entries.filter((entry) => entry.effectiveRole === tab);
}
