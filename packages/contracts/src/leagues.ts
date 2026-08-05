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
}

export interface LeagueRules {
  presetName: "standard";
  participantCount: number;
  participantMin: number;
  participantMax: number;
  roster: LeagueRosterConfig;
  totalCredits: number;
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
  role: "member" | "league_admin";
  joinedAt: string;
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
