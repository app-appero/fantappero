import { foldSearchText } from "../../utils/searchText";
import { filterListoneEntries, NO_LISTONE_PLACE_FILTERS } from "@fantappero/contracts";
import type {
  CreditAccount,
  CreditLedgerList,
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
  ListonePlaceFilters,
  RosterOccupancyEntry,
  RosterOwnershipSource,
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
export const ROSTER_PAGE_SIZE = 10;
export const LISTONE_PAGE_SIZE = 20;

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
  if (reason === "market_auction_win") {
    return "Asta vinta";
  }
  if (reason === "market_waiver_acquisition") {
    return "Acquisto da svincolati";
  }
  if (reason === "market_release_refund") {
    return "Rimborso svincolo";
  }
  if (reason === "market_trade_credits_sent") {
    return "Crediti inviati per scambio";
  }
  if (reason === "market_trade_credits_received") {
    return "Crediti ricevuti da scambio";
  }
  return reason;
}

const OWNERSHIP_SOURCE_LABEL: Record<RosterOwnershipSource, string> = {
  manual: "Inserimento manuale",
  csv_import: "Importazione da file",
  admin: "Assegnazione admin",
  market: "Mercato",
};

/**
 * Etichetta italiana dell'origine di un possesso nello storico della rosa (QA 19-20/11: si
 * vedeva il codice, «market» o «csv_import»). Un codice nuovo non ancora tradotto mostra «Altro».
 */
export function ownershipSourceLabel(source: string): string {
  return Object.prototype.hasOwnProperty.call(OWNERSHIP_SOURCE_LABEL, source)
    ? OWNERSHIP_SOURCE_LABEL[source as RosterOwnershipSource]
    : "Altro";
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

/**
 * Movimenti dal più recente. Il server li manda dal più vecchio, già nell'ordine in cui il
 * saldo si è mosso: a parità di orario (stesso millisecondo) si tiene quell'ordine, rovesciato.
 * Prima a parità si ordinava per id, che è casuale.
 */
export function sortLedgerNewestFirst(entries: CreditLedgerList["entries"]) {
  return entries
    .map((entry, index) => ({ entry, index, time: Date.parse(entry.createdAt) }))
    .sort((left, right) => right.time - left.time || right.index - left.index)
    .map(({ entry }) => entry);
}

export function formatLedgerEntry(entry: CreditLedgerList["entries"][number]): string {
  const sign = entry.amount > 0 ? "+" : "";
  const note = entry.note?.trim();
  const detail = note ? ` — ${note}` : "";
  return `${formatLedgerDate(entry.createdAt)} · ${reasonLabel(entry.reason)}${detail}: ${sign}${entry.amount} → saldo ${entry.balanceAfter}`;
}

/**
 * Listone filtrato per ruolo, testo, «Solo disponibili», campionato e squadra. La logica è
 * quella condivisa con l'app (`filterListoneEntries` in `@fantappero/contracts`), con la
 * ricerca senza accenti e con la codifica riparata del sito (`utils/searchText.ts`).
 */
export function filterListone(
  entries: LeagueListoneEntry[],
  tab: RoleTab,
  query: string,
  onlyFree = false,
  ownedAthleteIds?: ReadonlySet<string>,
  place: ListonePlaceFilters = NO_LISTONE_PLACE_FILTERS,
): LeagueListoneEntry[] {
  return filterListoneEntries(
    entries,
    { role: tab, query, onlyFree, competitionId: place.competitionId, clubId: place.clubId },
    { fold: foldSearchText, ownedAthleteIds },
  );
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
