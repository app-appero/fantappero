import type {
  CreditAccount,
  CreditLedgerList,
  FantasyRole,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
  RosterImportPreview,
  RosterOccupancyEntry,
  RosterOwnershipHistory,
  RosterTurnSnapshotDetail,
  RosterTurnSnapshotSummary,
} from "@fantappero/contracts";
import {
  Badge,
  Breadcrumb,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  PageContainer,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  TabList,
  TabPanel,
  Tabs,
  UiStatePanel,
} from "@fantappero/ui";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  assignRosterSlot,
  confirmRosterCsvImport,
  createRosterTurnSnapshot,
  downloadRosterCsvTemplate,
  ensureFantasyTeams,
  fetchFantasyTeamCreditsForAdmin,
  fetchFantasyTeamForAdmin,
  fetchFantasyTeams,
  fetchLeagueListone,
  fetchMyCreditMovements,
  fetchMyCredits,
  fetchMyFantasyTeam,
  fetchMyRosterHistory,
  fetchRosterOccupancy,
  fetchRosterTurnSnapshot,
  fetchRosterTurnSnapshots,
  fetchTeamRosterHistoryForAdmin,
  postAdminCreditMovement,
  previewRosterCsvImport,
  releaseRosterSlot,
} from "../api/leagues";
import { getApiErrorMessage, useAuth } from "../auth/AuthContext";
import { loadStoredSession } from "../auth/sessionStorage";
import { useLocation } from "../router/simpleRouter";
import { parseWireframeStateFromSearch } from "../wireframes/useWireframeState";

type RoleTab = "all" | FantasyRole;
type RosterPageSection = "rosa" | "storico";

const DEMO_HISTORY: RosterOwnershipHistory = {
  fantasyTeamId: "demo-team",
  intervals: [
    {
      id: "interval-1",
      fantasyTeamId: "demo-team",
      athleteId: "a1",
      athleteName: "L. Martinez",
      slotIndex: 0,
      purchaseCredits: 120,
      acquiredAt: "2026-08-01T10:00:00+00:00",
      releasedAt: null,
      source: "manual",
      active: true,
    },
    {
      id: "interval-2",
      fantasyTeamId: "demo-team",
      athleteId: "a9",
      athleteName: "Ex Calciatore",
      slotIndex: 1,
      purchaseCredits: 40,
      acquiredAt: "2026-07-01T10:00:00+00:00",
      releasedAt: "2026-07-20T10:00:00+00:00",
      source: "admin",
      active: false,
    },
  ],
};

const DEMO_SNAPSHOTS: RosterTurnSnapshotSummary[] = [
  {
    id: "snap-1",
    leagueId: "demo-league",
    roundNumber: 1,
    capturedAt: "2026-08-05T12:00:00+00:00",
    entryCount: 2,
    actorId: "demo-admin",
  },
];

const DEMO_SNAPSHOT_DETAIL: RosterTurnSnapshotDetail = {
  id: "snap-1",
  leagueId: "demo-league",
  roundNumber: 1,
  capturedAt: "2026-08-05T12:00:00+00:00",
  entryCount: 2,
  actorId: "demo-admin",
  created: false,
  entries: [
    {
      fantasyTeamId: "demo-team",
      teamName: "Rosa demo",
      slotIndex: 0,
      athleteId: "a1",
      athleteName: "L. Martinez",
      purchaseCredits: 120,
      role: "A",
    },
    {
      fantasyTeamId: "demo-team",
      teamName: "Rosa demo",
      slotIndex: 1,
      athleteId: "a2",
      athleteName: "N. Barella",
      purchaseCredits: 80,
      role: "C",
    },
  ],
};

type AthleteOwnership = {
  teamId: string;
  teamName: string;
  slotIndex: number;
};

const ROLE_TABS: Array<{ value: RoleTab; label: string }> = [
  { value: "all", label: "Tutti" },
  { value: "P", label: "Portieri" },
  { value: "D", label: "Difensori" },
  { value: "C", label: "Centrocampisti" },
  { value: "A", label: "Attaccanti" },
];

const ROLE_LABEL: Record<FantasyRole, string> = {
  P: "Portiere",
  D: "Difensore",
  C: "Centrocampista",
  A: "Attaccante",
};

const ROLE_SECTION_ORDER: FantasyRole[] = ["P", "D", "C", "A"];

const ROLE_SECTION_TITLE: Record<FantasyRole, string> = {
  P: "Portieri",
  D: "Difensori",
  C: "Centrocampisti",
  A: "Attaccanti",
};

const DEMO_COMPOSITION_LIMITS = {
  rosterSize: 35,
  goalkeepers: 3,
  defenders: 11,
  midfielders: 11,
  forwards: 10,
} as const;

const DEMO_TEAM: FantasyTeam = {
  id: "demo-team",
  leagueId: "demo-league",
  membershipId: "demo-membership",
  userId: "demo-user",
  name: "Rosa demo",
  rosterSize: 35,
  filledSlots: 2,
  compositionStatus: "incomplete",
  composition: {
    status: "incomplete",
    filledSlots: 2,
    competitionCount: 1,
    requireComplete: false,
    validatedAt: null,
    limits: { ...DEMO_COMPOSITION_LIMITS },
    counts: { P: 0, D: 0, C: 1, A: 1 },
    issues: [],
  },
  slots: [
    {
      id: "slot-0",
      slotIndex: 0,
      athleteId: "a1",
      athleteName: "L. Martinez",
      clubName: "Inter",
      role: "A",
      purchaseCredits: 50,
    },
    {
      id: "slot-1",
      slotIndex: 1,
      athleteId: "a2",
      athleteName: "N. Barella",
      clubName: "Inter",
      role: "C",
      purchaseCredits: 35,
    },
    ...Array.from({ length: 33 }, (_, index) => ({
      id: `slot-${index + 2}`,
      slotIndex: index + 2,
      athleteId: null,
      athleteName: null,
      clubName: null,
      role: null,
      purchaseCredits: null,
    })),
  ],
};

const DEMO_OCCUPANCY: RosterOccupancyEntry[] = [
  {
    athleteId: "a1",
    fantasyTeamId: DEMO_TEAM.id,
    teamName: DEMO_TEAM.name,
    slotIndex: 0,
    purchaseCredits: 50,
  },
  {
    athleteId: "a2",
    fantasyTeamId: DEMO_TEAM.id,
    teamName: DEMO_TEAM.name,
    slotIndex: 1,
    purchaseCredits: 35,
  },
];

const DEMO_TEAM_B: FantasyTeam = {
  ...DEMO_TEAM,
  id: "demo-team-b",
  membershipId: "demo-membership-b",
  userId: "demo-user-b",
  name: "Rosa avversaria",
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

const DEMO_TEAMS: FantasyTeamSummary[] = [
  {
    id: DEMO_TEAM.id,
    leagueId: DEMO_TEAM.leagueId,
    membershipId: DEMO_TEAM.membershipId,
    userId: DEMO_TEAM.userId,
    name: DEMO_TEAM.name,
    rosterSize: DEMO_TEAM.rosterSize,
    filledSlots: DEMO_TEAM.filledSlots,
    compositionStatus: DEMO_TEAM.compositionStatus,
  },
  {
    id: DEMO_TEAM_B.id,
    leagueId: DEMO_TEAM_B.leagueId,
    membershipId: DEMO_TEAM_B.membershipId,
    userId: DEMO_TEAM_B.userId,
    name: DEMO_TEAM_B.name,
    rosterSize: DEMO_TEAM_B.rosterSize,
    filledSlots: DEMO_TEAM_B.filledSlots,
    compositionStatus: DEMO_TEAM_B.compositionStatus,
  },
];

const DEMO_LISTONE: LeagueListoneEntry[] = [
  {
    athleteId: "a1",
    canonicalName: "L. Martinez",
    seasonYear: 2026,
    officialRole: "A",
    effectiveRole: "A",
    providerPositionRaw: "Attacker",
    mappingVersion: "v1.0.0",
    clubId: null,
    clubName: "Inter",
    override: null,
  },
  {
    athleteId: "a2",
    canonicalName: "N. Barella",
    seasonYear: 2026,
    officialRole: "C",
    effectiveRole: "C",
    providerPositionRaw: "Midfielder",
    mappingVersion: "v1.0.0",
    clubId: null,
    clubName: "Inter",
    override: null,
  },
  {
    athleteId: "a3",
    canonicalName: "R. Leao",
    seasonYear: 2026,
    officialRole: "A",
    effectiveRole: "A",
    providerPositionRaw: "Attacker",
    mappingVersion: "v1.0.0",
    clubId: null,
    clubName: "Milan",
    override: null,
  },
  {
    athleteId: "a4",
    canonicalName: "M. Thuram",
    seasonYear: 2026,
    officialRole: "A",
    effectiveRole: "A",
    providerPositionRaw: "Attacker",
    mappingVersion: "v1.0.0",
    clubId: null,
    clubName: "Inter",
    override: null,
  },
];

const DEMO_CREDITS: CreditAccount = {
  fantasyTeamId: "demo-team",
  balance: 940,
  version: 3,
  reconstructedBalance: 940,
};

const DEMO_LEDGER: CreditLedgerList = {
  fantasyTeamId: "demo-team",
  balance: 940,
  version: 3,
  entries: [
    {
      id: "entry-1",
      amount: 1000,
      reason: "initial_allocation",
      transactionId: "initial:demo-team",
      balanceAfter: 1000,
      note: "Allocazione iniziale crediti di lega",
      actorId: null,
      createdAt: "2026-08-01T10:00:00+00:00",
    },
    {
      id: "entry-2",
      amount: -50,
      reason: "roster_purchase",
      transactionId: "purchase:demo-team:0:a1",
      balanceAfter: 950,
      note: "Acquisto L. Martinez",
      actorId: "demo-user",
      createdAt: "2026-08-10T15:30:00+00:00",
    },
    {
      id: "entry-3",
      amount: -10,
      reason: "admin_adjustment",
      transactionId: "adj:demo-1",
      balanceAfter: 940,
      note: "Correzione manuale",
      actorId: "demo-admin",
      createdAt: "2026-08-11T09:00:00+00:00",
    },
  ],
};

const DEMO_CREDITS_B: CreditAccount = {
  fantasyTeamId: "demo-team-b",
  balance: 1000,
  version: 1,
  reconstructedBalance: 1000,
};

const DEMO_LEDGER_B: CreditLedgerList = {
  fantasyTeamId: "demo-team-b",
  balance: 1000,
  version: 1,
  entries: [
    {
      id: "entry-b1",
      amount: 1000,
      reason: "initial_allocation",
      transactionId: "initial:demo-team-b",
      balanceAfter: 1000,
      note: "Allocazione iniziale crediti di lega",
      actorId: null,
      createdAt: "2026-08-01T10:00:00+00:00",
    },
  ],
};

function reasonLabel(reason: string): string {
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

const LEDGER_PAGE_SIZE = 10;

function formatLedgerDate(iso: string): string {
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

function sortLedgerNewestFirst(entries: CreditLedgerList["entries"]) {
  return [...entries].sort((left, right) => {
    const leftTime = Date.parse(left.createdAt);
    const rightTime = Date.parse(right.createdAt);
    if (leftTime !== rightTime) {
      return rightTime - leftTime;
    }
    return right.id.localeCompare(left.id);
  });
}

function formatLedgerEntry(entry: CreditLedgerList["entries"][number]): string {
  const sign = entry.amount > 0 ? "+" : "";
  const note = entry.note?.trim();
  const detail = note ? ` — ${note}` : "";
  return `${formatLedgerDate(entry.createdAt)} · ${reasonLabel(entry.reason)}${detail}: ${sign}${entry.amount} → saldo ${entry.balanceAfter}`;
}

function filterByTab(entries: LeagueListoneEntry[], tab: RoleTab): LeagueListoneEntry[] {
  if (tab === "all") {
    return entries;
  }
  return entries.filter((entry) => entry.effectiveRole === tab);
}

function filterListone(
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

function buildOwnership(entries: RosterOccupancyEntry[]): Map<string, AthleteOwnership> {
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

function roleLabel(role: string | null): string {
  if (!role) {
    return "—";
  }
  if (role in ROLE_LABEL) {
    return ROLE_LABEL[role as FantasyRole];
  }
  return role;
}

function roleBadgeVariant(role: string | null | undefined): "success" | "warning" | "accent" | "danger" | "neutral" {
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

function toSummary(team: FantasyTeam): FantasyTeamSummary {
  return {
    id: team.id,
    leagueId: team.leagueId,
    membershipId: team.membershipId,
    userId: team.userId,
    name: team.name,
    rosterSize: team.rosterSize,
    filledSlots: team.filledSlots,
    compositionStatus: team.compositionStatus,
  };
}

function compositionStatusLabel(status: string | undefined): string {
  if (status === "validated") {
    return "Convalidata";
  }
  if (status === "invalid") {
    return "Non valida";
  }
  return "Incompleta";
}

function compositionStatusVariant(
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

function initialDemoTeam(
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

function initialDemoCredits(
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

function initialDemoLedger(
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

/** Rosa fantasy, ledger crediti e inserimento manuale admin (EP05-01/02/03).
 * EP05-04 CSV import UI is implemented but temporarily hidden (`SHOW_ROSTER_CSV_IMPORT`).
 */
const SHOW_ROSTER_CSV_IMPORT = false;

export function RosterPage() {
  const { isDemoMode, activeLeagueId, activeLeague, can } = useAuth();
  const { search } = useLocation();
  const demoState = isDemoMode ? parseWireframeStateFromSearch(search) : null;
  const isAdmin = can(["league:admin"]);
  const canView = can(["roster:view"]);
  const canEdit = can(["roster:edit"]);

  const [team, setTeam] = useState<FantasyTeam | null>(() =>
    initialDemoTeam(isDemoMode, demoState),
  );
  const [credits, setCredits] = useState<CreditAccount | null>(() =>
    initialDemoCredits(isDemoMode, demoState),
  );
  const [ledger, setLedger] = useState<CreditLedgerList | null>(() =>
    initialDemoLedger(isDemoMode, demoState),
  );
  const [loading, setLoading] = useState(() =>
    isDemoMode ? demoState === "loading" : true,
  );
  const [loadError, setLoadError] = useState<string | null>(() =>
    isDemoMode && demoState === "error"
      ? "Impossibile caricare i giocatori della rosa."
      : null,
  );
  const [ensureMessage, setEnsureMessage] = useState<string | null>(null);
  const [ensureError, setEnsureError] = useState<string | null>(null);
  const [ensuring, setEnsuring] = useState(false);
  const [adjustAmount, setAdjustAmount] = useState("-10");
  const [adjustNote, setAdjustNote] = useState("");
  const [adjustMessage, setAdjustMessage] = useState<string | null>(null);
  const [adjustError, setAdjustError] = useState<string | null>(null);
  const [adjusting, setAdjusting] = useState(false);

  const [leagueTeams, setLeagueTeams] = useState<FantasyTeamSummary[]>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? DEMO_TEAMS
      : [],
  );
  const [adminTeamId, setAdminTeamId] = useState(() =>
    isDemoMode ? DEMO_TEAM.id : "",
  );
  const [adminTeam, setAdminTeam] = useState<FantasyTeam | null>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? DEMO_TEAM
      : null,
  );
  const [teamDetails, setTeamDetails] = useState<FantasyTeam[]>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? [DEMO_TEAM, DEMO_TEAM_B]
      : [],
  );
  const [listone, setListone] = useState<LeagueListoneEntry[]>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? DEMO_LISTONE
      : [],
  );
  const [roleTab, setRoleTab] = useState<RoleTab>("all");
  const [listoneQuery, setListoneQuery] = useState("");
  const [purchaseCredits, setPurchaseCredits] = useState("1");
  const [occupancy, setOccupancy] = useState<RosterOccupancyEntry[]>(() =>
    isDemoMode && demoState !== "forbidden" && demoState !== "error" && demoState !== "loading"
      ? DEMO_OCCUPANCY
      : [],
  );
  const [adminBusy, setAdminBusy] = useState(false);
  const [adminMessage, setAdminMessage] = useState<string | null>(null);
  const [adminError, setAdminError] = useState<string | null>(null);
  const [adminLoadError, setAdminLoadError] = useState<string | null>(null);
  const [ledgerPage, setLedgerPage] = useState(0);
  const [csvPreview, setCsvPreview] = useState<RosterImportPreview | null>(null);
  const [csvResolutions, setCsvResolutions] = useState<Record<number, string>>({});
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvMessage, setCsvMessage] = useState<string | null>(null);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [pageSection, setPageSection] = useState<RosterPageSection>(() => {
    const params = new URLSearchParams(search);
    return params.get("sezione") === "storico" ? "storico" : "rosa";
  });
  const [history, setHistory] = useState<RosterOwnershipHistory | null>(() => {
    if (!isDemoMode || demoState === "forbidden" || demoState === "error" || demoState === "loading") {
      return null;
    }
    if (demoState === "empty") {
      return { fantasyTeamId: "demo-team", intervals: [] };
    }
    return DEMO_HISTORY;
  });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [snapshots, setSnapshots] = useState<RosterTurnSnapshotSummary[]>(() => {
    if (!isDemoMode || demoState === "forbidden" || demoState === "error" || demoState === "loading" || demoState === "empty") {
      return [];
    }
    return DEMO_SNAPSHOTS;
  });
  const [snapshotDetail, setSnapshotDetail] = useState<RosterTurnSnapshotDetail | null>(() => {
    if (!isDemoMode || demoState === "forbidden" || demoState === "error" || demoState === "loading" || demoState === "empty") {
      return null;
    }
    return DEMO_SNAPSHOT_DETAIL;
  });
  const [snapshotRound, setSnapshotRound] = useState("1");
  const [snapshotBusy, setSnapshotBusy] = useState(false);
  const [snapshotMessage, setSnapshotMessage] = useState<string | null>(null);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);
  const csvFileInputRef = useRef<HTMLInputElement | null>(null);
  const adminTeamIdRef = useRef(adminTeamId);
  adminTeamIdRef.current = adminTeamId;

  const ownership = useMemo(() => buildOwnership(occupancy), [occupancy]);

  const viewedTeam = isAdmin ? (adminTeam ?? team) : team;
  const targetTeam = viewedTeam;
  const targetTeamId = isAdmin ? adminTeamId : team?.id ?? "";

  const emptySlots = useMemo(
    () => targetTeam?.slots.filter((slot) => !slot.athleteId) ?? [],
    [targetTeam],
  );

  const canReleaseAthlete = useCallback(
    (ownerTeamId: string) => isAdmin || ownerTeamId === team?.id,
    [isAdmin, team?.id],
  );

  const applyTeamUpdate = useCallback((updated: FantasyTeam) => {
    setTeamDetails((current) => {
      const next = current.some((row) => row.id === updated.id)
        ? current.map((row) => (row.id === updated.id ? updated : row))
        : [...current, updated];
      return next;
    });
    setLeagueTeams((current) =>
      current.map((row) => (row.id === updated.id ? toSummary(updated) : row)),
    );
    setAdminTeam((current) => (current?.id === updated.id ? updated : current));
    setTeam((current) => (current?.id === updated.id ? updated : current));
    setOccupancy((current) => {
      const withoutTeam = current.filter((entry) => entry.fantasyTeamId !== updated.id);
      const fromTeam = updated.slots
        .filter((slot) => slot.athleteId)
        .map((slot) => ({
          athleteId: slot.athleteId!,
          fantasyTeamId: updated.id,
          teamName: updated.name,
          slotIndex: slot.slotIndex,
          purchaseCredits: slot.purchaseCredits,
        }));
      return [...withoutTeam, ...fromTeam];
    });
  }, []);

  const refreshMyCredits = useCallback(async (accessToken: string, leagueId: string) => {
    const [nextCredits, nextLedger] = await Promise.all([
      fetchMyCredits(accessToken, leagueId),
      fetchMyCreditMovements(accessToken, leagueId),
    ]);
    setCredits(nextCredits);
    setLedger(nextLedger);
    setLedgerPage(0);
  }, []);

  const applyLedgerResult = useCallback((result: CreditLedgerList) => {
    setCredits({
      fantasyTeamId: result.fantasyTeamId,
      balance: result.balance,
      version: result.version,
      reconstructedBalance: result.entries.reduce((sum, entry) => sum + entry.amount, 0),
    });
    setLedger(result);
    setLedgerPage(0);
  }, []);

  const refreshViewedCredits = useCallback(
    async (accessToken: string, leagueId: string) => {
      const viewedId = adminTeamIdRef.current;
      if (isAdmin && viewedId) {
        const result = await fetchFantasyTeamCreditsForAdmin(accessToken, leagueId, viewedId);
        applyLedgerResult(result);
        return;
      }
      await refreshMyCredits(accessToken, leagueId);
    },
    [applyLedgerResult, isAdmin, refreshMyCredits],
  );

  const applyDemoCreditDelta = useCallback((fantasyTeamId: string, delta: number) => {
    setCredits((current) => {
      if (!current || current.fantasyTeamId !== fantasyTeamId) {
        return current;
      }
      return { ...current, balance: current.balance + delta };
    });
  }, []);

  const loadEditContext = useCallback(
    async (preferredTeamId?: string) => {
      setAdminLoadError(null);
      if (!canEdit) {
        setLeagueTeams([]);
        setAdminTeam(null);
        setTeamDetails([]);
        setListone([]);
        setOccupancy([]);
        return;
      }

      if (isDemoMode) {
        if (demoState === "forbidden" || demoState === "error" || demoState === "loading") {
          setLeagueTeams([]);
          setAdminTeam(null);
          setTeamDetails([]);
          setListone([]);
          setOccupancy([]);
          return;
        }
        setListone(DEMO_LISTONE);
        setOccupancy(DEMO_OCCUPANCY);
        if (isAdmin) {
          setLeagueTeams(DEMO_TEAMS);
          setTeamDetails([DEMO_TEAM, DEMO_TEAM_B]);
          const nextId = preferredTeamId || adminTeamIdRef.current || DEMO_TEAM.id;
          setAdminTeamId(nextId);
          setAdminTeam(nextId === DEMO_TEAM.id ? DEMO_TEAM : DEMO_TEAM_B);
        }
        return;
      }

      if (!activeLeagueId) {
        setLeagueTeams([]);
        setAdminTeam(null);
        setTeamDetails([]);
        setListone([]);
        setOccupancy([]);
        return;
      }
      const stored = loadStoredSession();
      if (!stored?.accessToken) {
        setAdminLoadError("Sessione non disponibile. Accedi di nuovo.");
        return;
      }

      try {
        const [entries, occupancyData] = await Promise.all([
          fetchLeagueListone(stored.accessToken, activeLeagueId),
          fetchRosterOccupancy(stored.accessToken, activeLeagueId),
        ]);
        setListone(entries);
        setOccupancy(occupancyData);

        if (isAdmin) {
          const teams = await fetchFantasyTeams(stored.accessToken, activeLeagueId);
          setLeagueTeams(teams);
          const details = await Promise.all(
            teams.map((row) =>
              fetchFantasyTeamForAdmin(stored.accessToken, activeLeagueId, row.id),
            ),
          );
          setTeamDetails(details);
          const nextId = preferredTeamId || adminTeamIdRef.current || teams[0]?.id || "";
          setAdminTeamId(nextId);
          setAdminTeam(details.find((row) => row.id === nextId) ?? null);
        }
      } catch (error) {
        setAdminLoadError(
          getApiErrorMessage(error, "Impossibile caricare il listone e l'occupazione rosa."),
        );
        setAdminTeam(null);
        setTeamDetails([]);
      }
    },
    [activeLeagueId, canEdit, demoState, isAdmin, isDemoMode],
  );

  const loadRoster = useCallback(async () => {
    setEnsureMessage(null);
    setEnsureError(null);
    setAdjustMessage(null);
    setAdjustError(null);
    setAdminMessage(null);
    setAdminError(null);

    if (isDemoMode) {
      if (demoState === "loading") {
        setLoading(true);
        setTeam(null);
        setCredits(null);
        setLedger(null);
        setLoadError(null);
        return;
      }
      if (demoState === "error") {
        setLoading(false);
        setTeam(null);
        setCredits(null);
        setLedger(null);
        setLoadError("Impossibile caricare i giocatori della rosa.");
        return;
      }
      if (demoState === "empty") {
        setLoading(false);
        setTeam({
          ...DEMO_TEAM,
          filledSlots: 0,
          slots: DEMO_TEAM.slots.map((slot) => ({
            ...slot,
            athleteId: null,
            athleteName: null,
          })),
        });
        setCredits(DEMO_CREDITS);
        setLedger(DEMO_LEDGER);
        setLoadError(null);
        return;
      }
      if (demoState === "forbidden") {
        setLoading(false);
        setTeam(null);
        setCredits(null);
        setLedger(null);
        setLoadError(null);
        return;
      }
      setTeam(DEMO_TEAM);
      setCredits(DEMO_CREDITS);
      setLedger(DEMO_LEDGER);
      setLoading(false);
      setLoadError(null);
      return;
    }

    if (!canView) {
      setLoading(false);
      setTeam(null);
      setCredits(null);
      setLedger(null);
      setLoadError(null);
      return;
    }

    if (!activeLeagueId) {
      setLoading(false);
      setTeam(null);
      setCredits(null);
      setLedger(null);
      setLoadError(null);
      return;
    }

    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setLoading(false);
      setTeam(null);
      setCredits(null);
      setLedger(null);
      setLoadError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }

    setLoading(true);
    setLoadError(null);
    try {
      const [nextTeam, nextCredits, nextLedger] = await Promise.all([
        fetchMyFantasyTeam(stored.accessToken, activeLeagueId),
        fetchMyCredits(stored.accessToken, activeLeagueId),
        fetchMyCreditMovements(stored.accessToken, activeLeagueId),
      ]);
      setTeam(nextTeam);
      setCredits(nextCredits);
      setLedger(nextLedger);
    } catch (error) {
      setTeam(null);
      setCredits(null);
      setLedger(null);
      setLoadError(getApiErrorMessage(error, "Impossibile caricare i giocatori della rosa."));
    } finally {
      setLoading(false);
    }
  }, [activeLeagueId, canView, demoState, isDemoMode]);

  useEffect(() => {
    void loadRoster();
  }, [loadRoster]);

  useEffect(() => {
    void loadEditContext();
  }, [loadEditContext]);

  useEffect(() => {
    if (!canEdit || isAdmin || !team) {
      return;
    }
    setAdminTeamId(team.id);
    setAdminTeam(team);
  }, [canEdit, isAdmin, team]);

  const loadHistory = useCallback(async () => {
    setHistoryError(null);
    setSnapshotError(null);
    if (isDemoMode) {
      if (demoState === "forbidden" || demoState === "error" || demoState === "loading") {
        setHistory(null);
        setSnapshots([]);
        setSnapshotDetail(null);
        return;
      }
      if (demoState === "empty") {
        setHistory({ fantasyTeamId: "demo-team", intervals: [] });
        setSnapshots([]);
        setSnapshotDetail(null);
        return;
      }
      setHistory(DEMO_HISTORY);
      setSnapshots(DEMO_SNAPSHOTS);
      setSnapshotDetail(DEMO_SNAPSHOT_DETAIL);
      return;
    }
    if (!canView || !activeLeagueId) {
      setHistory(null);
      setSnapshots([]);
      setSnapshotDetail(null);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setHistoryError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setHistoryLoading(true);
    try {
      const historyPromise =
        isAdmin && adminTeamId
          ? fetchTeamRosterHistoryForAdmin(stored.accessToken, activeLeagueId, adminTeamId)
          : fetchMyRosterHistory(stored.accessToken, activeLeagueId);
      const [nextHistory, nextSnapshots] = await Promise.all([
        historyPromise,
        fetchRosterTurnSnapshots(stored.accessToken, activeLeagueId),
      ]);
      setHistory(nextHistory);
      setSnapshots(nextSnapshots);
      const preferred = nextSnapshots.at(-1);
      if (preferred) {
        setSnapshotRound(String(preferred.roundNumber));
        const detail = await fetchRosterTurnSnapshot(
          stored.accessToken,
          activeLeagueId,
          preferred.roundNumber,
          isAdmin && adminTeamId ? { teamId: adminTeamId } : undefined,
        );
        setSnapshotDetail(detail);
      } else {
        setSnapshotDetail(null);
      }
    } catch (error) {
      setHistory(null);
      setSnapshots([]);
      setSnapshotDetail(null);
      setHistoryError(getApiErrorMessage(error, "Impossibile caricare lo storico rosa."));
    } finally {
      setHistoryLoading(false);
    }
  }, [activeLeagueId, adminTeamId, canView, demoState, isAdmin, isDemoMode]);

  useEffect(() => {
    if (pageSection !== "storico") {
      return;
    }
    void loadHistory();
  }, [loadHistory, pageSection]);

  const onSelectSnapshotRound = async (roundValue: string) => {
    setSnapshotRound(roundValue);
    setSnapshotError(null);
    setSnapshotMessage(null);
    if (isDemoMode) {
      setSnapshotDetail(
        Number(roundValue) === DEMO_SNAPSHOT_DETAIL.roundNumber ? DEMO_SNAPSHOT_DETAIL : null,
      );
      return;
    }
    if (!activeLeagueId || !roundValue) {
      setSnapshotDetail(null);
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setSnapshotError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSnapshotBusy(true);
    try {
      const detail = await fetchRosterTurnSnapshot(
        stored.accessToken,
        activeLeagueId,
        Number(roundValue),
        isAdmin && adminTeamId ? { teamId: adminTeamId } : undefined,
      );
      setSnapshotDetail(detail);
    } catch (error) {
      setSnapshotDetail(null);
      setSnapshotError(getApiErrorMessage(error, "Snapshot turno non disponibile."));
    } finally {
      setSnapshotBusy(false);
    }
  };

  const onCreateSnapshot = async () => {
    setSnapshotError(null);
    setSnapshotMessage(null);
    const roundNumber = Number(snapshotRound);
    if (!Number.isInteger(roundNumber) || roundNumber < 1) {
      setSnapshotError("Indica un numero di turno valido (≥ 1).");
      return;
    }
    if (isDemoMode) {
      setSnapshotBusy(true);
      window.setTimeout(() => {
        setSnapshotMessage(`Snapshot turno ${roundNumber} creato (demo).`);
        setSnapshotDetail({
          ...DEMO_SNAPSHOT_DETAIL,
          roundNumber,
          created: true,
        });
        setSnapshots([
          {
            id: `snap-${roundNumber}`,
            leagueId: "demo-league",
            roundNumber,
            capturedAt: new Date().toISOString(),
            entryCount: DEMO_SNAPSHOT_DETAIL.entryCount,
            actorId: "demo-admin",
          },
        ]);
        setSnapshotBusy(false);
      }, 200);
      return;
    }
    if (!activeLeagueId) {
      setSnapshotError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setSnapshotError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setSnapshotBusy(true);
    try {
      const detail = await createRosterTurnSnapshot(stored.accessToken, activeLeagueId, {
        roundNumber,
      });
      setSnapshotDetail(detail);
      setSnapshotMessage(
        detail.created
          ? `Snapshot turno ${roundNumber} creato.`
          : `Snapshot turno ${roundNumber} già presente (idempotente).`,
      );
      const nextSnapshots = await fetchRosterTurnSnapshots(stored.accessToken, activeLeagueId);
      setSnapshots(nextSnapshots);
    } catch (error) {
      setSnapshotError(getApiErrorMessage(error, "Impossibile creare lo snapshot."));
    } finally {
      setSnapshotBusy(false);
    }
  };

  const onEnsureTeams = async () => {
    setEnsureMessage(null);
    setEnsureError(null);
    if (isDemoMode) {
      setEnsuring(true);
      window.setTimeout(() => {
        setEnsureMessage("Squadre verificate (demo).");
        setEnsuring(false);
      }, 300);
      return;
    }
    if (!activeLeagueId) {
      setEnsureError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setEnsureError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setEnsuring(true);
    try {
      const result = await ensureFantasyTeams(stored.accessToken, activeLeagueId);
      setEnsureMessage(
        `Squadre aggiornate: ${result.created} create, ${result.existing} già presenti.`,
      );
      setLeagueTeams(result.teams);
      await loadRoster();
      await loadEditContext(result.teams[0]?.id);
    } catch (error) {
      setEnsureError(getApiErrorMessage(error, "Impossibile creare le squadre."));
    } finally {
      setEnsuring(false);
    }
  };

  const onDownloadCsvTemplate = async () => {
    setCsvError(null);
    setCsvMessage(null);
    if (isDemoMode) {
      const blob = new Blob(
        ["squadra,provider_id,nome,crediti\nSquadra Esempio,12345,Nome Calciatore,10\n"],
        { type: "text/csv;charset=utf-8" },
      );
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "fantappero-import-rosa.csv";
      anchor.click();
      URL.revokeObjectURL(url);
      setCsvMessage("Modello CSV scaricato (demo).");
      return;
    }
    if (!activeLeagueId) {
      setCsvError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCsvError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    try {
      const blob = await downloadRosterCsvTemplate(stored.accessToken, activeLeagueId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "fantappero-import-rosa.csv";
      anchor.click();
      URL.revokeObjectURL(url);
      setCsvMessage("Modello CSV scaricato.");
    } catch (error) {
      setCsvError(getApiErrorMessage(error, "Impossibile scaricare il modello CSV."));
    }
  };

  const onCsvFileSelected = async (file: File | null) => {
    setCsvError(null);
    setCsvMessage(null);
    setCsvPreview(null);
    setCsvResolutions({});
    if (!file) {
      return;
    }
    if (isDemoMode) {
      setCsvBusy(true);
      window.setTimeout(() => {
        setCsvPreview({
          importId: "demo-import",
          status: "draft",
          fileSha256: "demo",
          originalFilename: file.name,
          canConfirm: true,
          rowCount: 1,
          errorCount: 0,
          warningCount: 0,
          confirmedAt: null,
          rows: [
            {
              rowNumber: 2,
              squadra: DEMO_TEAM.name,
              providerId: 1,
              nome: "L. Martinez",
              crediti: 10,
              status: "ok",
              fantasyTeamId: DEMO_TEAM.id,
              fantasyTeamName: DEMO_TEAM.name,
              athleteId: "a1",
              athleteName: "L. Martinez",
              slotIndex: 2,
              issues: [],
              candidates: [],
            },
          ],
        });
        setCsvBusy(false);
      }, 200);
      return;
    }
    if (!activeLeagueId) {
      setCsvError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCsvError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setCsvBusy(true);
    try {
      const preview = await previewRosterCsvImport(
        stored.accessToken,
        activeLeagueId,
        file,
      );
      setCsvPreview(preview);
      if (preview.errorCount > 0) {
        setCsvError("Anteprima con errori: correggi il file o risolvi le ambiguità.");
      }
    } catch (error) {
      setCsvError(getApiErrorMessage(error, "Impossibile elaborare il CSV."));
    } finally {
      setCsvBusy(false);
    }
  };

  const onConfirmCsvImport = async () => {
    setCsvError(null);
    setCsvMessage(null);
    if (!csvPreview) {
      setCsvError("Carica prima un file CSV.");
      return;
    }
    if (isDemoMode) {
      setCsvBusy(true);
      window.setTimeout(() => {
        setCsvMessage("Import CSV confermato (demo).");
        setCsvPreview(null);
        setCsvBusy(false);
      }, 200);
      return;
    }
    if (!activeLeagueId) {
      setCsvError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setCsvError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    const resolutions = Object.entries(csvResolutions).map(([rowNumber, athleteId]) => ({
      rowNumber: Number(rowNumber),
      athleteId,
    }));
    setCsvBusy(true);
    try {
      const result = await confirmRosterCsvImport(
        stored.accessToken,
        activeLeagueId,
        csvPreview.importId,
        { resolutions },
      );
      setCsvMessage(
        `Import completato: ${result.assignedCount} assegnazioni su ${result.teamsTouched} squadre.`,
      );
      setCsvPreview(null);
      setCsvResolutions({});
      await loadRoster();
      await loadEditContext(adminTeamId || undefined);
    } catch (error) {
      setCsvError(getApiErrorMessage(error, "Impossibile confermare l'import CSV."));
    } finally {
      setCsvBusy(false);
    }
  };

  const csvCanConfirm =
    !!csvPreview &&
    (csvPreview.canConfirm ||
      csvPreview.rows.every(
        (row) =>
          row.status === "ok" ||
          (row.status === "ambiguous" && Boolean(csvResolutions[row.rowNumber])),
      ));

  const onSelectAdminTeam = (teamId: string) => {
    setAdminTeamId(teamId);
    setAdminMessage(null);
    setAdminError(null);
    setAdjustMessage(null);
    setAdjustError(null);
    const detail = teamDetails.find((row) => row.id === teamId) ?? null;
    setAdminTeam(detail);

    if (isDemoMode) {
      if (teamId === DEMO_TEAM_B.id) {
        setCredits(DEMO_CREDITS_B);
        setLedger(DEMO_LEDGER_B);
      } else {
        setCredits(DEMO_CREDITS);
        setLedger(DEMO_LEDGER);
      }
      return;
    }

    if (!activeLeagueId) {
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      return;
    }
    void (async () => {
      try {
        const result = await fetchFantasyTeamCreditsForAdmin(
          stored.accessToken,
          activeLeagueId,
          teamId,
        );
        applyLedgerResult(result);
        if (!detail) {
          const fetched = await fetchFantasyTeamForAdmin(
            stored.accessToken,
            activeLeagueId,
            teamId,
          );
          setAdminTeam(fetched);
          setTeamDetails((current) =>
            current.some((row) => row.id === fetched.id)
              ? current.map((row) => (row.id === fetched.id ? fetched : row))
              : [...current, fetched],
          );
        }
      } catch {
        // Keep previous credits if the switch fails; assign/release will surface errors.
      }
    })();
  };

  const onAssignAthlete = async (athleteId: string) => {
    setAdminMessage(null);
    setAdminError(null);
    if (!targetTeamId || !targetTeam) {
      setAdminError("Seleziona una squadra.");
      return;
    }
    const emptySlot = emptySlots[0];
    if (!emptySlot) {
      setAdminError("Nessuno slot libero sulla squadra selezionata.");
      return;
    }
    if (ownership.has(athleteId)) {
      setAdminError("Il calciatore appartiene già a una squadra di questa lega.");
      return;
    }
    const credits = Number.parseInt(purchaseCredits, 10);
    if (!Number.isFinite(credits) || credits < 1) {
      setAdminError("Inserisci crediti acquisto validi (minimo 1).");
      return;
    }

    if (isDemoMode) {
      setAdminBusy(true);
      window.setTimeout(() => {
        const athlete = listone.find((entry) => entry.athleteId === athleteId);
        const updated: FantasyTeam = {
          ...targetTeam,
          slots: targetTeam.slots.map((slot) =>
            slot.slotIndex === emptySlot.slotIndex
              ? {
                  ...slot,
                  athleteId,
                  athleteName: athlete?.canonicalName ?? "Calciatore",
                  clubName: athlete?.clubName ?? null,
                  role: athlete?.effectiveRole ?? null,
                  purchaseCredits: credits,
                }
              : slot,
          ),
        };
        updated.filledSlots = updated.slots.filter((slot) => slot.athleteId).length;
        applyTeamUpdate(updated);
        applyDemoCreditDelta(updated.id, -credits);
        setAdminMessage(`${athlete?.canonicalName ?? "Calciatore"} assegnato (demo).`);
        setAdminBusy(false);
      }, 200);
      return;
    }

    if (!activeLeagueId) {
      setAdminError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setAdminError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setAdminBusy(true);
    try {
      const updated = await assignRosterSlot(
        stored.accessToken,
        activeLeagueId,
        targetTeamId,
        emptySlot.slotIndex,
        { athleteId, purchaseCredits: credits },
      );
      applyTeamUpdate(updated);
      await refreshViewedCredits(stored.accessToken, activeLeagueId);
      setAdminMessage(
        `Assegnato a slot ${emptySlot.slotIndex + 1}: ${
          updated.slots.find((slot) => slot.slotIndex === emptySlot.slotIndex)?.athleteName ??
          "calciatore"
        }.`,
      );
    } catch (error) {
      setAdminError(getApiErrorMessage(error, "Impossibile assegnare il calciatore."));
    } finally {
      setAdminBusy(false);
    }
  };

  const onReleaseAthlete = async (athleteId: string) => {
    setAdminMessage(null);
    setAdminError(null);
    const owner = ownership.get(athleteId);
    if (!owner) {
      setAdminError("Il calciatore non risulta in rosa.");
      return;
    }
    if (!canReleaseAthlete(owner.teamId)) {
      setAdminError("Non puoi rimuovere calciatori di altre squadre.");
      return;
    }

    if (isDemoMode) {
      setAdminBusy(true);
      window.setTimeout(() => {
        const current = isAdmin
          ? teamDetails.find((row) => row.id === owner.teamId)
          : team?.id === owner.teamId
            ? team
            : null;
        if (!current) {
          setAdminBusy(false);
          return;
        }
        const releasedSlot = current.slots.find((slot) => slot.slotIndex === owner.slotIndex);
        const refund = releasedSlot?.purchaseCredits ?? 0;
        const updated: FantasyTeam = {
          ...current,
          slots: current.slots.map((slot) =>
            slot.slotIndex === owner.slotIndex
              ? {
                  ...slot,
                  athleteId: null,
                  athleteName: null,
                  clubName: null,
                  role: null,
                  purchaseCredits: null,
                }
              : slot,
          ),
        };
        updated.filledSlots = updated.slots.filter((slot) => slot.athleteId).length;
        applyTeamUpdate(updated);
        applyDemoCreditDelta(owner.teamId, refund);
        setAdminMessage(`Rimosso da ${owner.teamName} (demo).`);
        setAdminBusy(false);
      }, 200);
      return;
    }

    if (!activeLeagueId) {
      setAdminError("Seleziona una lega.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setAdminError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    setAdminBusy(true);
    try {
      const updated = await releaseRosterSlot(
        stored.accessToken,
        activeLeagueId,
        owner.teamId,
        owner.slotIndex,
      );
      applyTeamUpdate(updated);
      await refreshViewedCredits(stored.accessToken, activeLeagueId);
      setAdminMessage(`Rimosso da ${owner.teamName}.`);
    } catch (error) {
      setAdminError(getApiErrorMessage(error, "Impossibile liberare lo slot."));
    } finally {
      setAdminBusy(false);
    }
  };

  const onAdminAdjust = async () => {
    setAdjustMessage(null);
    setAdjustError(null);
    const targetTeamId = adminTeamId || team?.id;
    if (isDemoMode) {
      setAdjusting(true);
      window.setTimeout(() => {
        setAdjustMessage("Movimento registrato (demo).");
        setAdjusting(false);
      }, 300);
      return;
    }
    if (!activeLeagueId || !targetTeamId) {
      setAdjustError("Seleziona una lega e una squadra.");
      return;
    }
    const stored = loadStoredSession();
    if (!stored?.accessToken) {
      setAdjustError("Sessione non disponibile. Accedi di nuovo.");
      return;
    }
    const amount = Number.parseInt(adjustAmount, 10);
    if (!Number.isFinite(amount) || amount === 0) {
      setAdjustError("Inserisci un importo diverso da zero.");
      return;
    }
    setAdjusting(true);
    try {
      const result = await postAdminCreditMovement(stored.accessToken, activeLeagueId, {
        fantasyTeamId: targetTeamId,
        amount,
        transactionId: `admin:${targetTeamId}:${Date.now()}`,
        note: adjustNote.trim() || null,
      });
      applyLedgerResult(result);
      setAdjustMessage(`Movimento registrato. Nuovo saldo: ${result.balance} crediti.`);
    } catch (error) {
      setAdjustError(getApiErrorMessage(error, "Impossibile registrare il movimento."));
    } finally {
      setAdjusting(false);
    }
  };

  const filledSlots = useMemo(
    () => viewedTeam?.slots.filter((slot) => slot.athleteId) ?? [],
    [viewedTeam?.slots],
  );
  const filledByRole = useMemo(() => {
    const groups: Record<FantasyRole | "unknown", typeof filledSlots> = {
      P: [],
      D: [],
      C: [],
      A: [],
      unknown: [],
    };
    for (const slot of filledSlots) {
      if (slot.role === "P" || slot.role === "D" || slot.role === "C" || slot.role === "A") {
        groups[slot.role].push(slot);
      } else {
        groups.unknown.push(slot);
      }
    }
    return groups;
  }, [filledSlots]);
  const compositionLimits = viewedTeam?.composition?.limits;
  const roleLimit = (role: FantasyRole): number | null => {
    if (!compositionLimits) {
      return null;
    }
    if (role === "P") {
      return compositionLimits.goalkeepers;
    }
    if (role === "D") {
      return compositionLimits.defenders;
    }
    if (role === "C") {
      return compositionLimits.midfielders;
    }
    return compositionLimits.forwards;
  };
  const isEmpty = Boolean(viewedTeam && viewedTeam.filledSlots === 0);
  const showForbidden = (isDemoMode && demoState === "forbidden") || (!isDemoMode && !canView);
  const hasLedger = Boolean(ledger && ledger.entries.length > 0);
  const ledgerEntriesNewestFirst = useMemo(
    () => (ledger ? sortLedgerNewestFirst(ledger.entries) : []),
    [ledger],
  );
  const ledgerPageCount = Math.max(1, Math.ceil(ledgerEntriesNewestFirst.length / LEDGER_PAGE_SIZE));
  const safeLedgerPage = Math.min(ledgerPage, ledgerPageCount - 1);
  const pagedLedgerEntries = ledgerEntriesNewestFirst.slice(
    safeLedgerPage * LEDGER_PAGE_SIZE,
    safeLedgerPage * LEDGER_PAGE_SIZE + LEDGER_PAGE_SIZE,
  );

  return (
    <PageContainer
      title="Rosa"
      density="compact"
      header={
        <Breadcrumb
          items={[
            { label: "Leghe", href: "/leghe" },
            { label: activeLeague?.name ?? "Rosa" },
          ]}
        />
      }
    >
      {loading ? (
        <UiStatePanel
          state="loading"
          title="Caricamento rosa"
          message="Recupero giocatori e crediti…"
          testId="roster-loading"
        />
      ) : null}

      {!loading && showForbidden ? (
        <UiStatePanel
          state="forbidden"
          title="Permessi insufficienti"
          message="Non hai i permessi per visualizzare la rosa."
          testId="roster-forbidden"
        />
      ) : null}

      {!loading && !showForbidden && !loadError ? (
        <div
          style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}
          data-testid="roster-section-tabs"
        >
          <Button
            type="button"
            variant={pageSection === "rosa" ? "primary" : "secondary"}
            data-testid="roster-section-rosa"
            onClick={() => setPageSection("rosa")}
          >
            Rosa
          </Button>
          <Button
            type="button"
            variant={pageSection === "storico" ? "primary" : "secondary"}
            data-testid="roster-section-storico"
            onClick={() => setPageSection("storico")}
          >
            Storico
          </Button>
        </div>
      ) : null}

      {!loading && !showForbidden && !loadError && pageSection === "storico" ? (
        <div data-testid="roster-history">
          {historyLoading ? (
            <UiStatePanel
              state="loading"
              title="Caricamento storico"
              message="Recupero intervalli di possesso e snapshot…"
              testId="roster-history-loading"
            />
          ) : null}
          {!historyLoading && historyError ? (
            <UiStatePanel
              state="error"
              title="Storico non disponibile"
              message={historyError}
              testId="roster-history-error"
            />
          ) : null}
          {!historyLoading && !historyError && history && history.intervals.length === 0 ? (
            <UiStatePanel
              state="empty"
              title="Nessun possesso registrato"
              message="Gli intervalli compaiono dopo assegnazioni o rilasci in rosa."
              testId="roster-history-empty"
            />
          ) : null}
          {!historyLoading && !historyError && history && history.intervals.length > 0 ? (
            <Card data-testid="roster-history-success">
              <CardHeader title="Intervalli di possesso" />
              <CardBody>
                <Table compact>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Calciatore</TableHeaderCell>
                      <TableHeaderCell>Slot</TableHeaderCell>
                      <TableHeaderCell>Crediti</TableHeaderCell>
                      <TableHeaderCell>Dal</TableHeaderCell>
                      <TableHeaderCell>Al</TableHeaderCell>
                      <TableHeaderCell>Fonte</TableHeaderCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {history.intervals.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell>{row.athleteName ?? row.athleteId}</TableCell>
                        <TableCell>{row.slotIndex + 1}</TableCell>
                        <TableCell>{row.purchaseCredits}</TableCell>
                        <TableCell>{new Date(row.acquiredAt).toLocaleString("it-IT")}</TableCell>
                        <TableCell>
                          {row.releasedAt
                            ? new Date(row.releasedAt).toLocaleString("it-IT")
                            : "In rosa"}
                        </TableCell>
                        <TableCell>{row.source}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardBody>
            </Card>
          ) : null}

          <Card style={{ marginTop: "1rem" }} data-testid="roster-snapshots">
            <CardHeader title="Snapshot per turno" />
            <CardBody>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "0.5rem",
                  alignItems: "center",
                  marginBottom: "0.75rem",
                }}
              >
                <label>
                  Turno{" "}
                  <input
                    data-testid="roster-snapshot-round"
                    value={snapshotRound}
                    onChange={(event) => setSnapshotRound(event.target.value)}
                    style={{ width: "4rem" }}
                  />
                </label>
                {snapshots.length > 0 ? (
                  <select
                    data-testid="roster-snapshot-select"
                    value={snapshotRound}
                    onChange={(event) => void onSelectSnapshotRound(event.target.value)}
                  >
                    {snapshots.map((row) => (
                      <option key={row.id} value={String(row.roundNumber)}>
                        Turno {row.roundNumber} ({row.entryCount} slot)
                      </option>
                    ))}
                  </select>
                ) : null}
                {isAdmin ? (
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={snapshotBusy}
                    data-testid="roster-snapshot-create"
                    onClick={() => void onCreateSnapshot()}
                  >
                    {snapshotBusy ? "Salvataggio…" : "Crea snapshot turno"}
                  </Button>
                ) : null}
                <Button
                  type="button"
                  variant="secondary"
                  disabled={snapshotBusy || !snapshotRound}
                  data-testid="roster-snapshot-load"
                  onClick={() => void onSelectSnapshotRound(snapshotRound)}
                >
                  Carica
                </Button>
              </div>
              {snapshotMessage ? (
                <p data-testid="roster-snapshot-ok">{snapshotMessage}</p>
              ) : null}
              {snapshotError ? (
                <p data-testid="roster-snapshot-error">{snapshotError}</p>
              ) : null}
              {!snapshotDetail ? (
                <UiStatePanel
                  state="empty"
                  title="Nessuno snapshot"
                  message="Crea uno snapshot per congelare la rosa di un turno."
                  testId="roster-snapshot-empty"
                />
              ) : (
                <div data-testid="roster-snapshot-detail">
                  <p>
                    Turno {snapshotDetail.roundNumber} · catturato{" "}
                    {new Date(snapshotDetail.capturedAt).toLocaleString("it-IT")} ·{" "}
                    {snapshotDetail.entryCount} assegnazioni
                  </p>
                  <Table compact>
                    <TableHead>
                      <TableRow>
                        <TableHeaderCell>Squadra</TableHeaderCell>
                        <TableHeaderCell>Calciatore</TableHeaderCell>
                        <TableHeaderCell>Ruolo</TableHeaderCell>
                        <TableHeaderCell>Crediti</TableHeaderCell>
                        <TableHeaderCell>Slot</TableHeaderCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {snapshotDetail.entries.map((entry) => (
                        <TableRow
                          key={`${entry.fantasyTeamId}-${entry.slotIndex}-${entry.athleteId}`}
                        >
                          <TableCell>{entry.teamName}</TableCell>
                          <TableCell>{entry.athleteName ?? entry.athleteId}</TableCell>
                          <TableCell>{roleLabel(entry.role)}</TableCell>
                          <TableCell>{entry.purchaseCredits}</TableCell>
                          <TableCell>{entry.slotIndex + 1}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && loadError ? (
        <div data-testid="roster-error-wrap">
          <UiStatePanel
            state="error"
            title="Rosa non disponibile"
            message={loadError}
            testId="roster-error"
          />
          <Button type="button" variant="secondary" onClick={() => void loadRoster()}>
            Ricarica
          </Button>
        </div>
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && !loadError && !activeLeagueId && !isDemoMode ? (
        <UiStatePanel
          state="empty"
          title="Nessuna lega attiva"
          message="Seleziona una lega per consultare la rosa."
          testId="roster-no-league"
        />
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && !loadError && (viewedTeam || team) ? (
        <div data-testid="roster-credits" style={{ marginBottom: "1rem" }}>
          {isAdmin && leagueTeams.length > 0 ? (
            <label
              style={{
                display: "flex",
                flexWrap: "wrap",
                alignItems: "center",
                gap: "0.5rem",
                marginBottom: "0.75rem",
              }}
            >
              <span style={{ fontWeight: 600 }}>Squadra target</span>
              <select
                data-testid="roster-admin-team"
                value={adminTeamId}
                onChange={(event) => onSelectAdminTeam(event.target.value)}
                disabled={adminBusy || adjusting}
                style={{ minWidth: "16rem", minHeight: "2.25rem" }}
              >
                {leagueTeams.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name} ({row.filledSlots}/{row.rosterSize})
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: "0.75rem 1rem",
              marginBottom: "0.5rem",
            }}
          >
            <p data-testid="roster-credits-balance" style={{ margin: 0 }}>
              Crediti residui: <strong>{credits?.balance ?? "—"}</strong>
              {credits ? ` (versione ${credits.version})` : null}
            </p>
            {isAdmin ? (
              <div
                data-testid="roster-admin-credits"
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  gap: "0.5rem",
                }}
              >
                <label>
                  Importo{" "}
                  <input
                    data-testid="roster-adjust-amount"
                    value={adjustAmount}
                    onChange={(event) => setAdjustAmount(event.target.value)}
                  />
                </label>
                <label>
                  Nota{" "}
                  <input
                    data-testid="roster-adjust-note"
                    value={adjustNote}
                    onChange={(event) => setAdjustNote(event.target.value)}
                  />
                </label>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={adjusting || !(adminTeamId || team)}
                  onClick={() => void onAdminAdjust()}
                >
                  {adjusting ? "Registrazione…" : "Aggiusta crediti"}
                </Button>
              </div>
            ) : null}
          </div>
          {adjustMessage ? <p data-testid="roster-adjust-ok">{adjustMessage}</p> : null}
          {adjustError ? <p data-testid="roster-adjust-error">{adjustError}</p> : null}
          {hasLedger ? (
            <div data-testid="roster-credits-ledger">
              <ul>
                {pagedLedgerEntries.map((entry) => (
                  <li key={entry.id}>{formatLedgerEntry(entry)}</li>
                ))}
              </ul>
              {ledgerEntriesNewestFirst.length > LEDGER_PAGE_SIZE ? (
                <div
                  style={{
                    display: "flex",
                    flexWrap: "wrap",
                    alignItems: "center",
                    gap: "0.5rem",
                    marginTop: "0.5rem",
                  }}
                >
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={safeLedgerPage <= 0}
                    data-testid="roster-credits-ledger-prev"
                    onClick={() => setLedgerPage((page) => Math.max(0, page - 1))}
                  >
                    Precedenti
                  </Button>
                  <span data-testid="roster-credits-ledger-page">
                    {safeLedgerPage + 1}/{ledgerPageCount}
                  </span>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={safeLedgerPage >= ledgerPageCount - 1}
                    data-testid="roster-credits-ledger-next"
                    onClick={() =>
                      setLedgerPage((page) => Math.min(ledgerPageCount - 1, page + 1))
                    }
                  >
                    Successivi
                  </Button>
                </div>
              ) : null}
            </div>
          ) : (
            <UiStatePanel
              state="empty"
              title="Nessun movimento"
              message="Il ledger crediti non contiene ancora movimenti."
              testId="roster-credits-empty"
            />
          )}
        </div>
      ) : null}

      {isAdmin && !showForbidden && !loading ? (
        <>
          {SHOW_ROSTER_CSV_IMPORT ? (
          <Card style={{ marginTop: "1rem" }} data-testid="roster-csv-import">
            <CardHeader>
              <h2 className="fa-auction-listone__title">Import CSV rose</h2>
            </CardHeader>
            <CardBody>
              <p>
                Scarica il modello, carica il file per l&apos;anteprima e conferma solo senza
                errori bloccanti. Nessuna scrittura avviene prima della conferma.
              </p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", marginTop: "0.75rem" }}>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={csvBusy}
                  onClick={() => void onDownloadCsvTemplate()}
                  data-testid="roster-csv-download"
                >
                  Scarica modello CSV
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={csvBusy}
                  onClick={() => csvFileInputRef.current?.click()}
                  data-testid="roster-csv-upload"
                >
                  {csvBusy ? "Elaborazione…" : "Carica CSV"}
                </Button>
                <input
                  ref={csvFileInputRef}
                  type="file"
                  accept=".csv,text/csv"
                  hidden
                  data-testid="roster-csv-file"
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    event.target.value = "";
                    void onCsvFileSelected(file);
                  }}
                />
                <Button
                  type="button"
                  disabled={csvBusy || !csvCanConfirm}
                  onClick={() => void onConfirmCsvImport()}
                  data-testid="roster-csv-confirm"
                >
                  Conferma import
                </Button>
              </div>
              {csvMessage ? (
                <UiStatePanel
                  state="success"
                  title="Import CSV"
                  message={csvMessage}
                  testId="roster-csv-ok"
                />
              ) : null}
              {csvError ? (
                <UiStatePanel
                  state="error"
                  title="Import CSV"
                  message={csvError}
                  testId="roster-csv-error"
                />
              ) : null}
              {csvPreview ? (
                <div style={{ marginTop: "1rem" }} data-testid="roster-csv-preview">
                  <p>
                    Anteprima: {csvPreview.rowCount} righe · errori {csvPreview.errorCount} ·
                    avvisi {csvPreview.warningCount}
                  </p>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableHeaderCell>Riga</TableHeaderCell>
                        <TableHeaderCell>Squadra</TableHeaderCell>
                        <TableHeaderCell>Calciatore</TableHeaderCell>
                        <TableHeaderCell>Crediti</TableHeaderCell>
                        <TableHeaderCell>Stato</TableHeaderCell>
                        <TableHeaderCell>Dettaglio</TableHeaderCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {csvPreview.rows.map((row) => (
                        <TableRow key={row.rowNumber}>
                          <TableCell>{row.rowNumber}</TableCell>
                          <TableCell>{row.fantasyTeamName ?? row.squadra}</TableCell>
                          <TableCell>{row.athleteName ?? row.nome ?? "—"}</TableCell>
                          <TableCell>{row.crediti ?? "—"}</TableCell>
                          <TableCell>{row.status}</TableCell>
                          <TableCell>
                            {row.issues.map((issue) => issue.message).join(" · ") || "—"}
                            {row.status === "ambiguous" ? (
                              <select
                                aria-label={`Risolvi riga ${row.rowNumber}`}
                                data-testid={`roster-csv-resolve-${row.rowNumber}`}
                                value={csvResolutions[row.rowNumber] ?? ""}
                                onChange={(event) =>
                                  setCsvResolutions((current) => ({
                                    ...current,
                                    [row.rowNumber]: event.target.value,
                                  }))
                                }
                              >
                                <option value="">Seleziona calciatore…</option>
                                {row.candidates.map((candidate) => (
                                  <option key={candidate.athleteId} value={candidate.athleteId}>
                                    {candidate.canonicalName} (#{candidate.providerId})
                                  </option>
                                ))}
                              </select>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : null}
            </CardBody>
          </Card>
          ) : null}

          <div style={{ marginTop: "1rem" }} data-testid="roster-admin-tools">
            <Button
              type="button"
              variant="secondary"
              disabled={ensuring}
              onClick={() => void onEnsureTeams()}
            >
              {ensuring ? "Verifica in corso…" : "Assicura squadre partecipanti"}
            </Button>
            {ensureMessage ? <p data-testid="roster-ensure-ok">{ensureMessage}</p> : null}
            {ensureError ? <p data-testid="roster-ensure-error">{ensureError}</p> : null}
          </div>
        </>
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && !loadError && viewedTeam && isEmpty ? (
        <div data-testid="roster-empty">
          <UiStatePanel
            state="empty"
            title="Rosa vuota"
            message="Completa l'asta o importa i giocatori per popolare la rosa."
          />
          <p data-testid="roster-empty-summary">
            {viewedTeam.name}: 0/{viewedTeam.rosterSize} slot occupati
          </p>
          <Button type="button" variant="secondary" onClick={() => void loadRoster()}>
            Ricarica
          </Button>
        </div>
      ) : null}

      {pageSection === "rosa" && !loading && !showForbidden && !loadError && viewedTeam && !isEmpty ? (
        <div data-testid="wireframe-roster-success">
          <p data-testid="roster-summary">
            {viewedTeam.name}: {viewedTeam.filledSlots}/{viewedTeam.rosterSize} giocatori
          </p>
          {viewedTeam.composition ? (
            <div data-testid="roster-composition">
              <p>
                Composizione:{" "}
                <Badge variant={compositionStatusVariant(viewedTeam.composition.status)}>
                  <span data-testid="roster-composition-status">
                    {compositionStatusLabel(viewedTeam.composition.status)}
                  </span>
                </Badge>
              </p>
              <p data-testid="roster-composition-counts">
                {viewedTeam.composition.counts.P}/{viewedTeam.composition.limits.goalkeepers}P ·{" "}
                {viewedTeam.composition.counts.D}/{viewedTeam.composition.limits.defenders}D ·{" "}
                {viewedTeam.composition.counts.C}/{viewedTeam.composition.limits.midfielders}C ·{" "}
                {viewedTeam.composition.counts.A}/{viewedTeam.composition.limits.forwards}A ·{" "}
                {viewedTeam.composition.competitionCount} campionati
              </p>
              {viewedTeam.composition.issues.length > 0 ? (
                <ul data-testid="roster-composition-issues">
                  {viewedTeam.composition.issues.map((issue) => (
                    <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          <div className="fa-roster-role-tables" data-testid="roster-filled-table">
            {ROLE_SECTION_ORDER.map((role) => {
              const slots = filledByRole[role];
              const limit = roleLimit(role);
              return (
                <section
                  key={role}
                  className="fa-roster-role-section"
                  data-testid={`roster-filled-table-${role}`}
                >
                  <h3 className="fa-roster-role-section__title">
                    <Badge variant={roleBadgeVariant(role)}>{role}</Badge>{" "}
                    {ROLE_SECTION_TITLE[role]}
                    <span className="fa-roster-role-section__count">
                      {slots.length}
                      {limit != null ? `/${limit}` : ""}
                    </span>
                  </h3>
                  {slots.length === 0 ? (
                    <p className="fa-roster-role-section__empty">Nessun giocatore in questo ruolo.</p>
                  ) : (
                    <Table compact>
                      <TableHead>
                        <TableRow>
                          <TableHeaderCell>Calciatore</TableHeaderCell>
                          <TableHeaderCell>Club</TableHeaderCell>
                          <TableHeaderCell>Crediti acquisto</TableHeaderCell>
                          <TableHeaderCell>Slot</TableHeaderCell>
                          {canEdit ? <TableHeaderCell>Azione</TableHeaderCell> : null}
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {slots.map((slot) => (
                          <TableRow key={slot.id}>
                            <TableCell>{slot.athleteName ?? "Calciatore"}</TableCell>
                            <TableCell>{slot.clubName ?? "—"}</TableCell>
                            <TableCell>{slot.purchaseCredits ?? "—"}</TableCell>
                            <TableCell>{slot.slotIndex + 1}</TableCell>
                            {canEdit ? (
                              <TableCell>
                                {slot.athleteId ? (
                                  <Button
                                    type="button"
                                    variant="secondary"
                                    disabled={adminBusy}
                                    data-testid={`roster-admin-release-${slot.athleteId}`}
                                    onClick={() => void onReleaseAthlete(slot.athleteId!)}
                                  >
                                    Rimuovi
                                  </Button>
                                ) : null}
                              </TableCell>
                            ) : null}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </section>
              );
            })}
            {filledByRole.unknown.length > 0 ? (
              <section
                className="fa-roster-role-section"
                data-testid="roster-filled-table-unknown"
              >
                <h3 className="fa-roster-role-section__title">
                  Senza ruolo
                  <span className="fa-roster-role-section__count">
                    {filledByRole.unknown.length}
                  </span>
                </h3>
                <Table compact>
                  <TableHead>
                    <TableRow>
                      <TableHeaderCell>Calciatore</TableHeaderCell>
                      <TableHeaderCell>Club</TableHeaderCell>
                      <TableHeaderCell>Crediti acquisto</TableHeaderCell>
                      <TableHeaderCell>Slot</TableHeaderCell>
                      {canEdit ? <TableHeaderCell>Azione</TableHeaderCell> : null}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {filledByRole.unknown.map((slot) => (
                      <TableRow key={slot.id}>
                        <TableCell>{slot.athleteName ?? "Calciatore"}</TableCell>
                        <TableCell>{slot.clubName ?? "—"}</TableCell>
                        <TableCell>{slot.purchaseCredits ?? "—"}</TableCell>
                        <TableCell>{slot.slotIndex + 1}</TableCell>
                        {canEdit ? (
                          <TableCell>
                            {slot.athleteId ? (
                              <Button
                                type="button"
                                variant="secondary"
                                disabled={adminBusy}
                                data-testid={`roster-admin-release-${slot.athleteId}`}
                                onClick={() => void onReleaseAthlete(slot.athleteId!)}
                              >
                                Rimuovi
                              </Button>
                            ) : null}
                          </TableCell>
                        ) : null}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </section>
            ) : null}
          </div>
        </div>
      ) : null}

      {pageSection === "rosa" && canEdit && !showForbidden ? (
        <Card style={{ marginTop: "1rem" }} data-testid="roster-admin-manual">
          <CardHeader>
            <div className="fa-auction-listone__header">
              <div>
                <h2 className="fa-auction-listone__title">Inserimento manuale rose</h2>
                <p className="fa-auction-listone__subtitle">
                  {isAdmin
                    ? "Assegna o rimuovi calciatori dal listone sulla squadra target selezionata sopra."
                    : "Assegna o rimuovi calciatori dal listone sulla tua rosa."}
                </p>
              </div>
            </div>
          </CardHeader>
          <CardBody>
            {adminLoadError ? (
              <UiStatePanel
                state="error"
                title="Caricamento non riuscito"
                message={adminLoadError}
                testId="roster-admin-manual-error"
              />
            ) : null}

            {isAdmin && leagueTeams.length === 0 ? (
              <UiStatePanel
                state="empty"
                title="Nessuna squadra"
                message="Assicura prima le squadre dei partecipanti."
                testId="roster-admin-manual-empty"
              />
            ) : !isAdmin && !targetTeam ? (
              <UiStatePanel
                state="empty"
                title="Nessuna squadra"
                message="La tua rosa non è ancora disponibile."
                testId="roster-admin-manual-empty"
              />
            ) : (
              <>
                {targetTeam ? (
                  <p data-testid="roster-admin-team-summary">
                    {targetTeam.name}: {targetTeam.filledSlots}/{targetTeam.rosterSize} slot ·{" "}
                    {emptySlots.length} liberi
                  </p>
                ) : null}

                <div style={{ marginBottom: "0.75rem" }}>
                  <Input
                    label="Crediti acquisto"
                    name="roster-purchase-credits"
                    type="number"
                    min={1}
                    value={purchaseCredits}
                    onChange={(event) => setPurchaseCredits(event.target.value)}
                    data-testid="roster-purchase-credits"
                  />
                </div>

                {adminMessage ? (
                  <UiStatePanel
                    state="success"
                    title="Operazione riuscita"
                    message={adminMessage}
                    testId="roster-admin-ok"
                  />
                ) : null}
                {adminError ? (
                  <UiStatePanel
                    state="error"
                    title="Operazione non riuscita"
                    message={adminError}
                    testId="roster-admin-assign-error"
                  />
                ) : null}

                {listone.length === 0 ? (
                  <UiStatePanel
                    state="empty"
                    title="Listone vuoto"
                    message="Il listone ufficiale non è ancora disponibile. Verrà popolato dagli operatori della piattaforma."
                    testId="roster-admin-listone-empty"
                  />
                ) : (
                  <>
                    <div
                      className="fa-roster-listone__search"
                      style={{ marginBottom: "0.75rem" }}
                    >
                      <Input
                        label="Cerca calciatore"
                        name="roster-listone-query"
                        value={listoneQuery}
                        placeholder="Nome o club…"
                        onChange={(event) => setListoneQuery(event.target.value)}
                        data-testid="roster-admin-listone-search"
                      />
                    </div>
                    <Tabs
                      value={roleTab}
                      onValueChange={(value) => setRoleTab(value as RoleTab)}
                      aria-label="Filtra listone per ruolo"
                    >
                      <TabList>
                        {ROLE_TABS.map((tab) => (
                          <Tab key={tab.value} value={tab.value}>
                            {tab.label}
                          </Tab>
                        ))}
                      </TabList>
                      {ROLE_TABS.map((tab) => {
                        const rows = filterListone(listone, tab.value, listoneQuery);
                        return (
                          <TabPanel key={tab.value} value={tab.value}>
                            {rows.length === 0 ? (
                              <UiStatePanel
                                state="empty"
                                title="Nessun calciatore"
                                message={
                                  listoneQuery.trim()
                                    ? "Nessun risultato per la ricerca corrente."
                                    : tab.value === "all"
                                      ? "Il listone è vuoto."
                                      : `Nessun ${ROLE_LABEL[tab.value as FantasyRole].toLowerCase()} nel listone.`
                                }
                                testId={`roster-admin-listone-empty-${tab.value}`}
                              />
                            ) : (
                              <Table
                                compact
                                data-testid={`roster-admin-listone-table-${tab.value}`}
                              >
                                <TableHead>
                                  <TableRow>
                                    <TableHeaderCell>Calciatore</TableHeaderCell>
                                    <TableHeaderCell>Ruolo</TableHeaderCell>
                                    <TableHeaderCell>Club</TableHeaderCell>
                                    <TableHeaderCell>Stato</TableHeaderCell>
                                    <TableHeaderCell>Azione</TableHeaderCell>
                                  </TableRow>
                                </TableHead>
                                <TableBody>
                                  {rows.map((entry) => {
                                    const owner = ownership.get(entry.athleteId);
                                    const canAssign = !owner && emptySlots.length > 0;
                                    const canRelease = owner
                                      ? canReleaseAthlete(owner.teamId)
                                      : false;
                                    return (
                                      <TableRow key={entry.athleteId}>
                                        <TableCell>{entry.canonicalName}</TableCell>
                                        <TableCell>
                                          <Badge variant={roleBadgeVariant(entry.effectiveRole)}>
                                            {entry.effectiveRole}
                                          </Badge>{" "}
                                          {ROLE_LABEL[entry.effectiveRole]}
                                        </TableCell>
                                        <TableCell>{entry.clubName ?? "—"}</TableCell>
                                        <TableCell>
                                          {owner ? (
                                            <Badge variant="warning">
                                              In rosa: {owner.teamName}
                                            </Badge>
                                          ) : (
                                            <Badge variant="success">Libero</Badge>
                                          )}
                                        </TableCell>
                                        <TableCell>
                                          {owner && canRelease ? (
                                            <Button
                                              type="button"
                                              variant="secondary"
                                              disabled={adminBusy}
                                              data-testid={`roster-admin-release-${entry.athleteId}`}
                                              onClick={() =>
                                                void onReleaseAthlete(entry.athleteId)
                                              }
                                            >
                                              Rimuovi
                                            </Button>
                                          ) : !owner ? (
                                            <Button
                                              type="button"
                                              variant="secondary"
                                              disabled={adminBusy || !canAssign}
                                              data-testid={`roster-admin-assign-${entry.athleteId}`}
                                              onClick={() =>
                                                void onAssignAthlete(entry.athleteId)
                                              }
                                            >
                                              Assegna
                                            </Button>
                                          ) : null}
                                        </TableCell>
                                      </TableRow>
                                    );
                                  })}
                                </TableBody>
                              </Table>
                            )}
                          </TabPanel>
                        );
                      })}
                    </Tabs>
                  </>
                )}
              </>
            )}
          </CardBody>
        </Card>
      ) : null}
    </PageContainer>
  );
}
