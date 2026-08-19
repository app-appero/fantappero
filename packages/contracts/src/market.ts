/** Market module contracts: auction/waiver sessions, releases, trades, history (EP08-01..08). */

export type MarketSessionKind = "initial_auction" | "waiver";

export type MarketSessionStatus = "scheduled" | "open" | "closed" | "resolved";

export type MarketBidStatus = "submitted" | "expired" | "won" | "lost" | "cancelled";

export type MarketReleaseReason = "voluntary" | "league_exit";

export type TradeStatus =
  | "proposed"
  | "cancelled"
  | "expired"
  | "accepted"
  | "rejected"
  | "countered"
  | "pending_approval"
  | "executed"
  | "rejected_by_admin";

export interface CreateMarketSessionRequest {
  opensAt: string;
  closesAt: string;
}

export interface MarketSession {
  id: string;
  leagueId: string;
  kind: MarketSessionKind;
  status: MarketSessionStatus;
  opensAt: string;
  closesAt: string;
  bidCount: number | null;
  parentSessionId: string | null;
  targetAthleteId: string | null;
}

export interface SubmitMarketBidRequest {
  amountCredits: number;
  /** Required for waiver bids (FR-MKT-01): the roster player to release if won. */
  releaseAthleteId?: string | null;
}

export interface MarketBid {
  id: string;
  sessionId: string;
  fantasyTeamId: string;
  athleteId: string;
  athleteName: string;
  amountCredits: number;
  status: MarketBidStatus;
  submittedAt: string;
  releaseAthleteId: string | null;
  releaseAthleteName: string | null;
}

export interface MarketBidList {
  sessionId: string;
  fantasyTeamId: string;
  bids: MarketBid[];
}

export type MarketResolutionOutcomeKind = "assigned" | "tiebreak" | "unassigned";

export interface MarketResolutionOutcome {
  athleteId: string;
  athleteName: string;
  outcome: MarketResolutionOutcomeKind;
  winningTeamId: string | null;
  amountCredits: number | null;
  tiebreakSessionId: string | null;
}

export interface MarketResolution {
  sessionId: string;
  status: MarketSessionStatus;
  outcomes: MarketResolutionOutcome[];
}

export interface MarketReleaseRequest {
  reason: MarketReleaseReason;
}

export interface MarketReleasePreview {
  fantasyTeamId: string;
  slotIndex: number;
  athleteId: string;
  athleteName: string;
  purchaseCredits: number;
  reason: MarketReleaseReason;
  refundPercent: number;
  refundCredits: number;
}

export interface MarketReleaseResult extends MarketReleasePreview {
  balance: number;
}

export interface CreateTradeProposalRequest {
  recipientTeamId: string;
  offeredAthleteIds: string[];
  requestedAthleteIds: string[];
  offeredCredits: number;
  requestedCredits: number;
  expiresAt: string;
}

export interface CounterTradeProposalRequest {
  offeredAthleteIds: string[];
  requestedAthleteIds: string[];
  offeredCredits: number;
  requestedCredits: number;
  expiresAt: string;
}

export interface TradeAthlete {
  id: string;
  name: string;
}

export interface TradeProposal {
  id: string;
  leagueId: string;
  proposerTeamId: string;
  recipientTeamId: string;
  offeredAthletes: TradeAthlete[];
  requestedAthletes: TradeAthlete[];
  offeredCredits: number;
  requestedCredits: number;
  status: TradeStatus;
  expiresAt: string;
  createdAt: string;
  counterOfId: string | null;
}

export interface TradeProposalList {
  proposals: TradeProposal[];
}

export type MarketHistoryCategory = "acquisto" | "svincolo" | "scambio" | "intervento_manuale";

export interface MarketHistoryEntry {
  id: string;
  occurredAt: string;
  category: MarketHistoryCategory;
  action: string;
  actorId: string;
  details: Record<string, unknown> | null;
}

export interface MarketHistoryList {
  items: MarketHistoryEntry[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface MarketHistoryFilters {
  category?: MarketHistoryCategory;
  fantasyTeamId?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}
