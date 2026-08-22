import type {
  CreditAccount,
  CreditLedgerList,
  FantasyTeam,
  FantasyTeamSummary,
  LeagueListoneEntry,
  RosterOccupancyEntry,
  RosterOwnershipHistory,
  RosterTurnSnapshotDetail,
  RosterTurnSnapshotSummary,
} from "@fantappero/contracts";

export const DEMO_HISTORY: RosterOwnershipHistory = {
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

export const DEMO_SNAPSHOTS: RosterTurnSnapshotSummary[] = [
  {
    id: "snap-1",
    leagueId: "demo-league",
    roundNumber: 1,
    capturedAt: "2026-08-05T12:00:00+00:00",
    entryCount: 2,
    actorId: "demo-admin",
  },
];

export const DEMO_SNAPSHOT_DETAIL: RosterTurnSnapshotDetail = {
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

export const DEMO_COMPOSITION_LIMITS = {
  rosterSize: 35,
  goalkeepers: 3,
  defenders: 11,
  midfielders: 11,
  forwards: 10,
} as const;

export const DEMO_TEAM: FantasyTeam = {
  id: "demo-team",
  leagueId: "demo-league",
  membershipId: "demo-membership",
  userId: "demo-user",
  userType: "human",
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

export const DEMO_OCCUPANCY: RosterOccupancyEntry[] = [
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

export const DEMO_TEAM_B: FantasyTeam = {
  ...DEMO_TEAM,
  id: "demo-team-b",
  membershipId: "demo-membership-b",
  userId: "demo-user-b",
  userType: "ai",
  name: "Allenatore IA 01",
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

export const DEMO_TEAMS: FantasyTeamSummary[] = [
  {
    id: DEMO_TEAM.id,
    leagueId: DEMO_TEAM.leagueId,
    membershipId: DEMO_TEAM.membershipId,
    userId: DEMO_TEAM.userId,
    userType: DEMO_TEAM.userType,
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
    userType: DEMO_TEAM_B.userType,
    name: DEMO_TEAM_B.name,
    rosterSize: DEMO_TEAM_B.rosterSize,
    filledSlots: DEMO_TEAM_B.filledSlots,
    compositionStatus: DEMO_TEAM_B.compositionStatus,
  },
];

export const DEMO_LISTONE: LeagueListoneEntry[] = [
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

export const DEMO_CREDITS: CreditAccount = {
  fantasyTeamId: "demo-team",
  balance: 940,
  version: 3,
  reconstructedBalance: 940,
};

export const DEMO_LEDGER: CreditLedgerList = {
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

export const DEMO_CREDITS_B: CreditAccount = {
  fantasyTeamId: "demo-team-b",
  balance: 1000,
  version: 1,
  reconstructedBalance: 1000,
};

export const DEMO_LEDGER_B: CreditLedgerList = {
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
