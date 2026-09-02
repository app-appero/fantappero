import type {
  CreditAccount,
  CreditLedgerList,
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
  RosterOccupancyEntry,
} from "@fantappero/contracts";
import { parseWireframeStateFromSearch } from "../../wireframes/useWireframeState";
import {
  DEMO_COMPOSITION_LIMITS,
  DEMO_CREDITS,
  DEMO_LEDGER,
  DEMO_TEAM,
} from "./rosterDemoData";

export type RoleTab = "all" | FantasyRole;
export type RosterPageSection = "rosa" | "storico";

export type AthleteOwnership = {
  teamId: string;
  teamName: string;
  slotIndex: number;
};

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

export const ROLE_SECTION_ORDER: FantasyRole[] = ["P", "D", "C", "A"];

export const ROLE_SECTION_TITLE: Record<FantasyRole, string> = {
  P: "Portieri",
  D: "Difensori",
  C: "Centrocampisti",
  A: "Attaccanti",
};

export const LEDGER_PAGE_SIZE = 10;

export function reasonLabel(reason: string): string {
  if (reason === "initial_allocation") {
    return "Allocazione iniziale";
  }
  if (reason === "admin_adjustment") {
    return "Aggiustamento admin";
  }
  if (reason === "roster_purchase") {
    return "Acquisto rosa";
  }
  if (reason === "roster_release_refund") {
    return "Rimborso rosa";
  }
  return reason;
}

export function formatLedgerDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("it-IT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function sortLedgerNewestFirst(entries: CreditLedgerList["entries"]) {
  return [...entries].sort((left, right) => {
    const leftTime = Date.parse(left.createdAt);
    const rightTime = Date.parse(right.createdAt);
    if (leftTime !== rightTime) {
      return rightTime - leftTime;
    }
    return right.id.localeCompare(left.id);
  });
}

export function formatLedgerEntry(entry: CreditLedgerList["entries"][number]): string {
  const sign = entry.amount > 0 ? "+" : "";
  const note = entry.note?.trim();
  const detail = note ? ` — ${note}` : "";
  return `${formatLedgerDate(entry.createdAt)} · ${reasonLabel(entry.reason)}${detail}: ${sign}${entry.amount} → saldo ${entry.balanceAfter}`;
}

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

export function buildOwnership(entries: RosterOccupancyEntry[]): Map<string, AthleteOwnership> {
  const map = new Map<string, AthleteOwnership>();
  for (const entry of entries) {
    map.set(entry.athleteId, {
      teamId: entry.fantasyTeamId,
      teamName: entry.teamName,
      slotIndex: entry.slotIndex,
    });
  }
  return map;
}

export function roleLabel(role: string | null): string {
  if (!role) {
    return "—";
  }
  if (role in ROLE_LABEL) {
    return ROLE_LABEL[role as FantasyRole];
  }
  return role;
}

export function roleBadgeVariant(
  role: string | null | undefined,
): "success" | "warning" | "accent" | "danger" | "neutral" {
  if (role === "P") {
    return "success";
  }
  if (role === "D") {
    return "warning";
  }
  if (role === "C") {
    return "accent";
  }
  if (role === "A") {
    return "danger";
  }
  return "neutral";
}

export function toSummary(team: FantasyTeam): FantasyTeamSummary {
  return {
    id: team.id,
    leagueId: team.leagueId,
    membershipId: team.membershipId,
    userId: team.userId,
    userType: team.userType,
    name: team.name,
    rosterSize: team.rosterSize,
    filledSlots: team.filledSlots,
    compositionStatus: team.compositionStatus,
  };
}

export function compositionStatusLabel(status: string | undefined): string {
  if (status === "validated") {
    return "Convalidata";
  }
  if (status === "invalid") {
    return "Non valida";
  }
  return "Incompleta";
}

export function compositionStatusVariant(
  status: string | undefined,
): "success" | "warning" | "danger" | "neutral" {
  if (status === "validated") {
    return "success";
  }
  if (status === "invalid") {
    return "danger";
  }
  return "warning";
}

export function initialDemoTeam(
  isDemoMode: boolean,
  demoState: ReturnType<typeof parseWireframeStateFromSearch> | null,
): FantasyTeam | null {
  if (!isDemoMode) {
    return null;
  }
  if (demoState === "error" || demoState === "loading" || demoState === "forbidden") {
    return null;
  }
  if (demoState === "empty") {
    return {
      ...DEMO_TEAM,
      filledSlots: 0,
      compositionStatus: "incomplete",
      composition: {
        status: "incomplete",
        filledSlots: 0,
        competitionCount: 0,
        requireComplete: false,
        validatedAt: null,
        limits: { ...DEMO_COMPOSITION_LIMITS },
        counts: { P: 0, D: 0, C: 0, A: 0 },
        issues: [],
      },
      slots: DEMO_TEAM.slots.map((slot) => ({
        ...slot,
        athleteId: null,
        athleteName: null,
        clubName: null,
        role: null,
        purchaseCredits: null,
      })),
    };
  }
  return DEMO_TEAM;
}

export function initialDemoCredits(
  isDemoMode: boolean,
  demoState: ReturnType<typeof parseWireframeStateFromSearch> | null,
): CreditAccount | null {
  if (!isDemoMode) {
    return null;
  }
  if (demoState === "error" || demoState === "loading" || demoState === "forbidden") {
    return null;
  }
  return DEMO_CREDITS;
}

export function initialDemoLedger(
  isDemoMode: boolean,
  demoState: ReturnType<typeof parseWireframeStateFromSearch> | null,
): CreditLedgerList | null {
  if (!isDemoMode) {
    return null;
  }
  if (demoState === "error" || demoState === "loading" || demoState === "forbidden") {
    return null;
  }
  return DEMO_LEDGER;
}
