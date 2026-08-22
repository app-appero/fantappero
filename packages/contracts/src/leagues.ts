/** League configuration contracts (EP03-02). */

export type LeagueState =
  | "draft"
  | "configuring"
  | "auction"
  | "active"
  | "concluded"
  | "archived";

export interface LeagueLifecycleBlocker {
  code: string;
  message: string;
}

export interface LeagueLifecycle {
  state: LeagueState;
  allowedTransitions: LeagueState[];
  blockers: LeagueLifecycleBlocker[];
}

export interface TransitionLeagueStateRequest {
  targetState: LeagueState;
}

/** Competition available in the MVP catalog. */
export interface CompetitionSummary {
  id: string;
  providerId: number;
  name: string;
  country: string;
}

export interface LeagueRosterConfig {
  rosterSize: number;
  goalkeepers: number;
  defenders: number;
  midfielders: number;
  forwards: number;
}

export interface LeagueRulesOptions {
  allowTrades: boolean;
  allowManualInvites: boolean;
  /** Defer trade execution to admin approval instead of executing on accept (EP08-07). */
  requireTradeApproval: boolean;
}

export interface LeagueRules {
  presetName: "standard";
  participantCount: number;
  participantMin: number;
  participantMax: number;
  roster: LeagueRosterConfig;
  totalCredits: number;
  /** Minimum real fixtures required to publish a european turn (10–40, default 25). */
  minFixturesPerRound: number;
  /** Minutes required for a statistical vote (1–30, default 15). */
  minutesThreshold: number;
  /** Credit refund percent for a voluntary release (0–100, EP08-04). */
  voluntaryReleaseRefundPercent: number;
  /** Credit refund percent for a release on exit from all five leagues (0–100, EP08-04). */
  leagueExitRefundPercent: number;
  /** Cap on a team's simultaneously active trade proposals (EP08-07). */
  maxActiveTradeProposalsPerTeam: number;
  options: LeagueRulesOptions;
}

/** Detailed league view including selected competitions. */
export interface LeagueDetail {
  id: string;
  name: string;
  seasonYear: number;
  state: LeagueState;
  viewerRole: "member" | "league_admin" | null;
  competitions: CompetitionSummary[];
  rules: LeagueRules | null;
}

export interface CreateLeagueRequest {
  name: string;
  seasonYear: number;
  competitionIds: string[];
}

export interface UpdateLeagueRulesRequest {
  presetName: "standard";
  participantCount: number;
  roster: LeagueRosterConfig;
  totalCredits: number;
  minFixturesPerRound?: number;
  minutesThreshold?: number;
  voluntaryReleaseRefundPercent?: number;
  leagueExitRefundPercent?: number;
  maxActiveTradeProposalsPerTeam?: number;
  options: LeagueRulesOptions;
}

export interface LeagueAdminPanel {
  leagueId: string;
  message: string;
  rules: LeagueRules;
  lifecycle: LeagueLifecycle;
}

export interface LeagueMember {
  userId: string;
  displayName: string;
  userType: import("./profile.js").UserType;
  role: "member" | "league_admin";
  joinedAt: string;
}

/** Classifica lega persistita (EP07-06 / FR-CLS-01). */
export interface LeagueStanding {
  fantasyTeamId: string;
  teamName: string;
  position: number;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  fantasyGoalsFor: number;
  fantasyGoalsAgainst: number;
  points: number;
  computedAt: string;
}

export type LeagueInviteStatus = "active" | "expired" | "revoked";

export interface CreateLeagueInviteRequest {
  expiresInDays: number;
}

export interface LeagueInvite {
  id: string;
  leagueId: string;
  status: LeagueInviteStatus;
  expiresAt: string;
  revokedAt: string | null;
  createdAt: string;
}

export interface CreatedLeagueInvite extends LeagueInvite {
  token: string;
  code: string;
  inviteUrl: string;
}

export type AcceptLeagueInviteRequest =
  | { token: string; code?: never }
  | { code: string; token?: never };

export interface AcceptedLeagueInvite {
  leagueId: string;
  leagueName: string;
  alreadyMember: boolean;
}

export type NamedLeagueInviteStatus =
  | "pending"
  | "accepted"
  | "declined"
  | "revoked"
  | "expired";

export interface FantasyCoachDirectoryItem {
  userId: string;
  displayName: string;
  avatarUrl: string | null;
  userType: import("./profile.js").UserType;
  availableForInvites: boolean;
  namedInviteStatus: NamedLeagueInviteStatus | null;
}

export interface PaginatedFantasyCoachDirectory {
  items: FantasyCoachDirectoryItem[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface CreateNamedLeagueInviteRequest {
  recipientUserId: string;
  expiresInDays?: number;
}

export interface NamedLeagueInvite {
  id: string;
  leagueId: string;
  leagueName: string;
  recipientUserId: string;
  recipientDisplayName: string;
  recipientUserType: import("./profile.js").UserType;
  status: NamedLeagueInviteStatus;
  expiresAt: string;
  respondedAt: string | null;
  createdAt: string;
  autoAccepted: boolean;
}

export interface RespondedNamedLeagueInvite extends NamedLeagueInvite {
  alreadyProcessed: boolean;
}

export type LeagueCalendarStatus = "draft" | "confirmed";
export type LeagueCalendarFormat = "single_round_robin";

export interface LeagueCalendarMatchup {
  slotIndex: number;
  isBye: boolean;
  homeUserId: string;
  homeDisplayName: string;
  awayUserId: string | null;
  awayDisplayName: string | null;
}

export interface LeagueCalendarRound {
  roundNumber: number;
  matchups: LeagueCalendarMatchup[];
}

export interface LeagueCalendar {
  id: string;
  leagueId: string;
  status: LeagueCalendarStatus;
  format: LeagueCalendarFormat;
  algorithmVersion: string;
  participantCount: number;
  roundCount: number;
  matchupCount: number;
  byeCount: number;
  generatedAt: string;
  confirmedAt: string | null;
  rounds: LeagueCalendarRound[];
  summary: { message: string };
}

export type FantasyRole = "P" | "D" | "C" | "A";

/** Risultato H2H persistito sullo slot (EP07-05), lettura matchday. */
export interface H2HMatchupScore {
  homeScore: number | null;
  awayScore: number | null;
  homeFantasyGoals: number | null;
  awayFantasyGoals: number | null;
  outcome: "home" | "away" | "draw" | null;
  resultFinal: boolean;
  computedAt: string | null;
}

export interface H2HCalendarMatchup {
  slotId: string;
  slotIndex: number;
  isBye: boolean;
  homeUserId: string;
  homeDisplayName: string;
  homeTeamName: string | null;
  awayUserId: string | null;
  awayDisplayName: string | null;
  awayTeamName: string | null;
  result: H2HMatchupScore | null;
}

export interface H2HCalendarRound {
  roundNumber: number;
  /** Allineato a FantasyRound.number sulla stessa lega. */
  fantasyRoundId: string | null;
  homologationStatus: "provisional" | "homologated" | null;
  europeanTurnStatus: "scheduled" | "open" | "locked" | "skipped" | null;
  matchups: H2HCalendarMatchup[];
}

export interface H2HCalendar {
  id: string;
  leagueId: string;
  status: "confirmed";
  format: LeagueCalendarFormat;
  algorithmVersion: string;
  participantCount: number;
  roundCount: number;
  matchupCount: number;
  byeCount: number;
  generatedAt: string;
  confirmedAt: string | null;
  /** True se almeno un turno europeo collegato è open/locked e non omologato. */
  live: boolean;
  rounds: H2HCalendarRound[];
  summary: { message: string };
}

export interface H2HPlayerScore {
  athleteId: string;
  name: string;
  role: FantasyRole;
  fantasyScore: number | null;
  isEffectiveStarter: boolean;
  isBench: boolean;
}

export interface H2HSideLineup {
  fantasyTeamId: string | null;
  teamName: string | null;
  displayName: string;
  module: string | null;
  lineupSource: "effective" | "submitted" | "none";
  totalScore: number | null;
  fantasyGoals: number | null;
  starters: H2HPlayerScore[];
  bench: H2HPlayerScore[];
}

export interface H2HMatchupDetail {
  slotId: string;
  leagueId: string;
  roundNumber: number;
  fantasyRoundId: string | null;
  homologationStatus: "provisional" | "homologated" | null;
  europeanTurnStatus: "scheduled" | "open" | "locked" | "skipped" | null;
  live: boolean;
  isBye: boolean;
  home: H2HSideLineup;
  away: H2HSideLineup | null;
  result: H2HMatchupScore | null;
}

export interface LeagueListoneOverride {
  role: FantasyRole;
  effectiveFromRound: number | null;
  pending: boolean;
  reason: string | null;
}

export interface LeagueListoneEntry {
  athleteId: string;
  canonicalName: string;
  seasonYear: number;
  officialRole: FantasyRole;
  effectiveRole: FantasyRole;
  providerPositionRaw: string | null;
  mappingVersion: string;
  clubId: string | null;
  clubName: string | null;
  override: LeagueListoneOverride | null;
}

export interface LeagueListoneRefreshCounters {
  athletesCreated: number;
  athletesUpdated: number;
  membershipsCreated: number;
  membershipsUpdated: number;
  transfersCreated: number;
  listoneCreated: number;
  listoneUpdated: number;
  listoneUnchanged: number;
  listoneSkippedUnmapped: number;
  catalogSynced: boolean;
}

export interface LeagueListoneRefreshResult {
  seasonYear: number;
  mappingVersion: string;
  refreshedAt: string;
  message: string;
  counters: LeagueListoneRefreshCounters;
}

export interface LeagueListoneRefreshJob {
  jobId: string;
  status: string;
  message: string;
}

export interface LeagueListoneRefreshProgress {
  jobId: string;
  leagueId: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  percent: number;
  stage: string;
  message: string;
  errorCode?: string | null;
  result?: LeagueListoneRefreshResult | null;
}

/** Fantasy team and roster slots (EP05-01 / EP05-03 / EP05-05). */
export type RosterCompositionStatus = "incomplete" | "invalid" | "validated";

export interface RosterCompositionLimits {
  rosterSize: number;
  goalkeepers: number;
  defenders: number;
  midfielders: number;
  forwards: number;
}

export interface RosterCompositionCounts {
  P: number;
  D: number;
  C: number;
  A: number;
}

export interface RosterCompositionIssue {
  code: string;
  message: string;
}

export interface RosterComposition {
  status: RosterCompositionStatus | string;
  filledSlots: number;
  competitionCount: number;
  requireComplete: boolean;
  validatedAt: string | null;
  limits: RosterCompositionLimits;
  counts: RosterCompositionCounts;
  issues: RosterCompositionIssue[];
}

export interface FantasyRosterSlot {
  id: string;
  slotIndex: number;
  athleteId: string | null;
  athleteName: string | null;
  clubName: string | null;
  role: string | null;
  purchaseCredits: number | null;
}

export interface FantasyTeam {
  id: string;
  leagueId: string;
  membershipId: string;
  userId: string;
  userType: import("./profile.js").UserType;
  name: string;
  rosterSize: number;
  filledSlots: number;
  compositionStatus: RosterCompositionStatus | string;
  composition?: RosterComposition | null;
  slots: FantasyRosterSlot[];
}

export interface FantasyTeamSummary {
  id: string;
  leagueId: string;
  membershipId: string;
  userId: string;
  userType: import("./profile.js").UserType;
  name: string;
  rosterSize: number;
  filledSlots: number;
  compositionStatus: RosterCompositionStatus | string;
}

export interface EnsureFantasyTeamsResult {
  created: number;
  existing: number;
  teams: FantasyTeamSummary[];
}

export interface AssignRosterSlotRequest {
  athleteId: string;
  purchaseCredits: number;
}

export interface RosterOccupancyEntry {
  athleteId: string;
  fantasyTeamId: string;
  teamName: string;
  athleteName?: string | null;
  slotIndex: number;
  purchaseCredits: number | null;
}

/** Giocatori in rosa di una squadra, per proposte di scambio. */
export interface TeamRosterPlayer {
  athleteId: string;
  athleteName: string;
  slotIndex: number;
  purchaseCredits: number | null;
}

/** Credit ledger (EP05-02 / EP05-03). */
export type CreditLedgerReason =
  | "initial_allocation"
  | "admin_adjustment"
  | "roster_purchase"
  | "roster_release_refund";

export interface CreditAccount {
  fantasyTeamId: string;
  balance: number;
  version: number;
  reconstructedBalance: number;
}

export interface CreditLedgerEntry {
  id: string;
  amount: number;
  reason: CreditLedgerReason | string;
  transactionId: string;
  balanceAfter: number;
  note: string | null;
  actorId: string | null;
  createdAt: string;
}

export interface CreditLedgerList {
  fantasyTeamId: string;
  balance: number;
  version: number;
  entries: CreditLedgerEntry[];
}

export interface AdminCreditMovementRequest {
  fantasyTeamId: string;
  amount: number;
  transactionId: string;
  note?: string | null;
}

/** CSV roster import with preview (EP05-04 / FR-ROS-03). */
export type RosterImportStatus = "draft" | "confirmed";

export type RosterImportRowStatus = "ok" | "error" | "ambiguous";

export interface RosterImportIssue {
  code: string;
  message: string;
  severity: "error" | "warning" | string;
}

export interface RosterImportAthleteCandidate {
  athleteId: string;
  providerId: number;
  canonicalName: string;
}

export interface RosterImportRow {
  rowNumber: number;
  squadra: string;
  providerId: number | null;
  nome: string;
  crediti: number | null;
  status: RosterImportRowStatus | string;
  fantasyTeamId: string | null;
  fantasyTeamName: string | null;
  athleteId: string | null;
  athleteName: string | null;
  slotIndex: number | null;
  issues: RosterImportIssue[];
  candidates: RosterImportAthleteCandidate[];
}

export interface RosterImportPreview {
  importId: string;
  status: RosterImportStatus | string;
  fileSha256: string;
  originalFilename: string | null;
  canConfirm: boolean;
  rowCount: number;
  errorCount: number;
  warningCount: number;
  rows: RosterImportRow[];
  confirmedAt: string | null;
}

export interface RosterImportResolution {
  rowNumber: number;
  athleteId: string;
}

export interface RosterImportConfirmRequest {
  resolutions?: RosterImportResolution[];
}

export interface RosterImportConfirmResult {
  importId: string;
  status: RosterImportStatus | string;
  assignedCount: number;
  teamsTouched: number;
  confirmedAt: string;
  preview: RosterImportPreview;
}

/** Roster ownership history and turn snapshots (EP05-06). */
export type RosterOwnershipSource = "manual" | "csv_import" | "admin";

export interface RosterOwnershipInterval {
  id: string;
  fantasyTeamId: string;
  athleteId: string;
  athleteName: string | null;
  slotIndex: number;
  purchaseCredits: number;
  acquiredAt: string;
  releasedAt: string | null;
  source: RosterOwnershipSource | string;
  active: boolean;
}

export interface RosterOwnershipHistory {
  fantasyTeamId: string;
  intervals: RosterOwnershipInterval[];
}

export interface RosterAsOfSlot {
  slotIndex: number;
  athleteId: string;
  athleteName: string | null;
  purchaseCredits: number;
  acquiredAt: string;
  role: string | null;
}

export interface RosterAsOf {
  fantasyTeamId: string;
  asOf: string;
  filledSlots: number;
  slots: RosterAsOfSlot[];
}

export interface CreateRosterTurnSnapshotRequest {
  roundNumber: number;
}

export interface RosterTurnSnapshotSummary {
  id: string;
  leagueId: string;
  roundNumber: number;
  capturedAt: string;
  entryCount: number;
  actorId: string | null;
}

export interface RosterTurnSnapshotEntry {
  fantasyTeamId: string;
  teamName: string;
  slotIndex: number;
  athleteId: string;
  athleteName: string | null;
  purchaseCredits: number;
  role: string | null;
}

export interface RosterTurnSnapshotDetail {
  id: string;
  leagueId: string;
  roundNumber: number;
  capturedAt: string;
  entryCount: number;
  actorId: string | null;
  created: boolean;
  entries: RosterTurnSnapshotEntry[];
}
