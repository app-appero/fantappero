import type {
  CreditLedgerList,
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  RosterOccupancyEntry,
} from "@fantappero/contracts";
import { theme } from "@fantappero/ui/theme";

const { colors } = theme;

export type AthleteOwnership = {
  teamId: string;
  teamName: string;
  slotIndex: number;
};

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

export const LEDGER_PAGE_SIZE = 10;

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

export function roleBadgeColors(
  role: string | null | undefined,
): { backgroundColor: string; color: string } {
  if (role === "P") {
    return { backgroundColor: colors.success, color: colors.accentContrast };
  }
  if (role === "D") {
    return { backgroundColor: colors.warning, color: colors.background };
  }
  if (role === "C") {
    return { backgroundColor: colors.accent, color: colors.accentContrast };
  }
  if (role === "A") {
    return { backgroundColor: colors.danger, color: colors.accentContrast };
  }
  return { backgroundColor: colors.border, color: colors.foreground };
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
