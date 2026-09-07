/** Market module contracts: auction/waiver sessions, releases, trades, history (EP08-01..08). */

import type { FantasyRole } from "./leagues.js";

export type MarketSessionKind = "initial_auction" | "waiver" | "live_auction";

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
  /** Optional: omit or send null for a proposal that never expires on its own. */
  expiresAt: string | null;
}

export interface CounterTradeProposalRequest {
  offeredAthleteIds: string[];
  requestedAthleteIds: string[];
  offeredCredits: number;
  requestedCredits: number;
  expiresAt: string | null;
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
  expiresAt: string | null;
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

/** Live/ascending auction: sessione, lotti e rilanci (EP08-09).
 *
 * Modalità distinta dalle buste chiuse sopra — un lotto (un calciatore) alla
 * volta, con rilanci visibili a tutti i partecipanti nel momento in cui
 * vengono piazzati, invece di offerte segrete risolte in un unico passaggio.
 */

export type MarketLiveNominationMode = "manual" | "sequential";

export type MarketLiveLotStatus = "open" | "sold" | "passed" | "cancelled" | "pending_swap";

export interface CreateLiveAuctionSessionRequest {
  opensAt: string;
  closesAt: string;
  nominationMode: MarketLiveNominationMode;
  minIncrementCredits: number;
  softCloseSeconds: number;
  lotDurationSeconds: number;
  operatorUserId?: string | null;
  /** Richiesto, non vuoto, solo se nominationMode è "sequential". */
  nominationQueueAthleteIds?: string[] | null;
}

export interface ConfigureLiveAuctionSessionRequest {
  minIncrementCredits?: number | null;
  softCloseSeconds?: number | null;
  lotDurationSeconds?: number | null;
  operatorUserId?: string | null;
  nominationQueueAthleteIds?: string[] | null;
}

export interface LiveAuctionSession {
  id: string;
  leagueId: string;
  status: MarketSessionStatus;
  opensAt: string;
  closesAt: string;
  nominationMode: MarketLiveNominationMode;
  minIncrementCredits: number;
  softCloseSeconds: number;
  lotDurationSeconds: number;
  operatorUserId: string | null;
  queueRemaining: number;
  pendingSwapCount: number;
}

export interface NominateLotRequest {
  /** Richiesto solo in modalità "manual"; ignorato in "sequential". */
  athleteId?: string | null;
}

export interface PlaceRaiseRequest {
  amountCredits: number;
}

export interface LiveLot {
  id: string;
  sessionId: string;
  athleteId: string;
  athleteName: string;
  sequenceNumber: number;
  status: MarketLiveLotStatus;
  openedAt: string;
  closesAt: string;
  minIncrementCredits: number;
  currentLeaderTeamId: string | null;
  currentLeaderTeamName: string | null;
  currentAmountCredits: number;
  minimumNextAmountCredits: number;
  closedAt: string | null;
}

export interface LiveRaise {
  id: string;
  lotId: string;
  fantasyTeamId: string;
  fantasyTeamName: string;
  amountCredits: number;
  placedAt: string;
}

export interface LiveSwapCandidate {
  slotIndex: number;
  athleteId: string;
  athleteName: string;
  purchaseCredits: number;
}

export interface PendingSwapDecision {
  lotId: string;
  athleteId: string;
  athleteName: string;
  amountCredits: number;
  role: FantasyRole;
  roleLabel: string;
  candidates: LiveSwapCandidate[];
}

export interface ResolveSwapRequest {
  releaseAthleteId: string;
}

export interface LiveLotState {
  session: LiveAuctionSession;
  currentLot: LiveLot | null;
  recentRaises: LiveRaise[];
  secondsRemaining: number | null;
  pendingSwap: PendingSwapDecision | null;
}

export interface LiveLotList {
  sessionId: string;
  lots: LiveLot[];
}
