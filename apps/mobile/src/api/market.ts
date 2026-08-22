import type {
  CounterTradeProposalRequest,
  CreateMarketSessionRequest,
  CreateTradeProposalRequest,
  MarketBid,
  MarketBidList,
  MarketHistoryFilters,
  MarketHistoryList,
  MarketReleasePreview,
  MarketReleaseReason,
  MarketReleaseResult,
  MarketResolution,
  MarketSession,
  SubmitMarketBidRequest,
  TradeProposal,
  TradeProposalList,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

// -- Asta a buste chiuse (EP08-01/02) -----------------------------------------

export function createAuctionSession(
  accessToken: string,
  leagueId: string,
  body: CreateMarketSessionRequest,
): Promise<MarketSession> {
  return apiRequest<MarketSession>(`/leagues/${leagueId}/mercato/asta/sessioni`, {
    accessToken,
    method: "POST",
    body,
  });
}

export function closeAuctionSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<MarketSession> {
  return apiRequest<MarketSession>(
    `/leagues/${leagueId}/mercato/asta/sessioni/${sessionId}/chiudi`,
    { accessToken, method: "POST" },
  );
}

export function resolveAuctionSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<MarketResolution> {
  return apiRequest<MarketResolution>(
    `/leagues/${leagueId}/mercato/asta/sessioni/${sessionId}/risolvi`,
    { accessToken, method: "POST" },
  );
}

export function fetchAuctionSessions(
  accessToken: string,
  leagueId: string,
): Promise<MarketSession[]> {
  return apiRequest<MarketSession[]>(`/leagues/${leagueId}/mercato/asta/sessioni`, {
    accessToken,
  });
}

export function fetchAuctionSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<MarketSession> {
  return apiRequest<MarketSession>(`/leagues/${leagueId}/mercato/asta/sessioni/${sessionId}`, {
    accessToken,
  });
}

export function submitAuctionBid(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  athleteId: string,
  body: SubmitMarketBidRequest,
): Promise<MarketBid> {
  return apiRequest<MarketBid>(
    `/leagues/${leagueId}/mercato/asta/sessioni/${sessionId}/offerte/${athleteId}`,
    { accessToken, method: "PUT", body },
  );
}

export function withdrawAuctionBid(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  athleteId: string,
): Promise<void> {
  return apiRequest<void>(
    `/leagues/${leagueId}/mercato/asta/sessioni/${sessionId}/offerte/${athleteId}`,
    { accessToken, method: "DELETE" },
  );
}

export function fetchMyAuctionBids(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<MarketBidList> {
  return apiRequest<MarketBidList>(
    `/leagues/${leagueId}/mercato/asta/sessioni/${sessionId}/offerte`,
    { accessToken },
  );
}

// -- Mercato svincolati / waiver (EP08-03) ------------------------------------

export function createWaiverSession(
  accessToken: string,
  leagueId: string,
  body: CreateMarketSessionRequest,
): Promise<MarketSession> {
  return apiRequest<MarketSession>(`/leagues/${leagueId}/mercato/svincoli/sessioni`, {
    accessToken,
    method: "POST",
    body,
  });
}

export function closeWaiverSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<MarketSession> {
  return apiRequest<MarketSession>(
    `/leagues/${leagueId}/mercato/svincoli/sessioni/${sessionId}/chiudi`,
    { accessToken, method: "POST" },
  );
}

export function resolveWaiverSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<MarketResolution> {
  return apiRequest<MarketResolution>(
    `/leagues/${leagueId}/mercato/svincoli/sessioni/${sessionId}/risolvi`,
    { accessToken, method: "POST" },
  );
}

export function fetchWaiverSessions(
  accessToken: string,
  leagueId: string,
): Promise<MarketSession[]> {
  return apiRequest<MarketSession[]>(`/leagues/${leagueId}/mercato/svincoli/sessioni`, {
    accessToken,
  });
}

export function fetchWaiverSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<MarketSession> {
  return apiRequest<MarketSession>(`/leagues/${leagueId}/mercato/svincoli/sessioni/${sessionId}`, {
    accessToken,
  });
}

export function submitWaiverBid(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  athleteId: string,
  body: SubmitMarketBidRequest,
): Promise<MarketBid> {
  return apiRequest<MarketBid>(
    `/leagues/${leagueId}/mercato/svincoli/sessioni/${sessionId}/offerte/${athleteId}`,
    { accessToken, method: "PUT", body },
  );
}

export function withdrawWaiverBid(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  athleteId: string,
): Promise<void> {
  return apiRequest<void>(
    `/leagues/${leagueId}/mercato/svincoli/sessioni/${sessionId}/offerte/${athleteId}`,
    { accessToken, method: "DELETE" },
  );
}

export function fetchMyWaiverBids(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<MarketBidList> {
  return apiRequest<MarketBidList>(
    `/leagues/${leagueId}/mercato/svincoli/sessioni/${sessionId}/offerte`,
    { accessToken },
  );
}

// -- Svincolo volontario e recupero crediti (EP08-04) -------------------------

export function previewVoluntaryRelease(
  accessToken: string,
  leagueId: string,
  slotIndex: number,
  reason: MarketReleaseReason,
): Promise<MarketReleasePreview> {
  const params = new URLSearchParams({ causa: reason });
  return apiRequest<MarketReleasePreview>(
    `/leagues/${leagueId}/mercato/svincolo/${slotIndex}/anteprima?${params.toString()}`,
    { accessToken },
  );
}

export function applyVoluntaryRelease(
  accessToken: string,
  leagueId: string,
  slotIndex: number,
  reason: MarketReleaseReason,
): Promise<MarketReleaseResult> {
  return apiRequest<MarketReleaseResult>(`/leagues/${leagueId}/mercato/svincolo/${slotIndex}`, {
    accessToken,
    method: "POST",
    body: { reason },
  });
}

// -- Scambi tra partecipanti (EP08-05/06/07) -----------------------------------

export function createTradeProposal(
  accessToken: string,
  leagueId: string,
  body: CreateTradeProposalRequest,
): Promise<TradeProposal> {
  return apiRequest<TradeProposal>(`/leagues/${leagueId}/mercato/scambi/proposte`, {
    accessToken,
    method: "POST",
    body,
  });
}

export function fetchTradeProposals(
  accessToken: string,
  leagueId: string,
): Promise<TradeProposalList> {
  return apiRequest<TradeProposalList>(`/leagues/${leagueId}/mercato/scambi/proposte`, {
    accessToken,
  });
}

export function fetchTradeProposal(
  accessToken: string,
  leagueId: string,
  proposalId: string,
): Promise<TradeProposal> {
  return apiRequest<TradeProposal>(`/leagues/${leagueId}/mercato/scambi/proposte/${proposalId}`, {
    accessToken,
  });
}

export function cancelTradeProposal(
  accessToken: string,
  leagueId: string,
  proposalId: string,
): Promise<TradeProposal> {
  return apiRequest<TradeProposal>(
    `/leagues/${leagueId}/mercato/scambi/proposte/${proposalId}/annulla`,
    { accessToken, method: "POST" },
  );
}

export function acceptTradeProposal(
  accessToken: string,
  leagueId: string,
  proposalId: string,
): Promise<TradeProposal> {
  return apiRequest<TradeProposal>(
    `/leagues/${leagueId}/mercato/scambi/proposte/${proposalId}/accetta`,
    { accessToken, method: "POST" },
  );
}

export function rejectTradeProposal(
  accessToken: string,
  leagueId: string,
  proposalId: string,
): Promise<TradeProposal> {
  return apiRequest<TradeProposal>(
    `/leagues/${leagueId}/mercato/scambi/proposte/${proposalId}/rifiuta`,
    { accessToken, method: "POST" },
  );
}

export function counterTradeProposal(
  accessToken: string,
  leagueId: string,
  proposalId: string,
  body: CounterTradeProposalRequest,
): Promise<TradeProposal> {
  return apiRequest<TradeProposal>(
    `/leagues/${leagueId}/mercato/scambi/proposte/${proposalId}/controproponi`,
    { accessToken, method: "POST", body },
  );
}

// -- Approvazione amministratore (EP08-07) -------------------------------------

export function approveTradeProposal(
  accessToken: string,
  leagueId: string,
  proposalId: string,
): Promise<TradeProposal> {
  return apiRequest<TradeProposal>(
    `/leagues/${leagueId}/mercato/scambi/proposte/${proposalId}/amministrazione/approva`,
    { accessToken, method: "POST" },
  );
}

export function rejectTradeProposalAsAdmin(
  accessToken: string,
  leagueId: string,
  proposalId: string,
): Promise<TradeProposal> {
  return apiRequest<TradeProposal>(
    `/leagues/${leagueId}/mercato/scambi/proposte/${proposalId}/amministrazione/rifiuta`,
    { accessToken, method: "POST" },
  );
}

// -- Storico mercato (EP08-08) -------------------------------------------------

export function fetchMarketHistory(
  accessToken: string,
  leagueId: string,
  filters: MarketHistoryFilters = {},
): Promise<MarketHistoryList> {
  const params = new URLSearchParams();
  if (filters.category) {
    params.set("category", filters.category);
  }
  if (filters.fantasyTeamId) {
    params.set("fantasyTeamId", filters.fantasyTeamId);
  }
  if (filters.dateFrom) {
    params.set("dateFrom", filters.dateFrom);
  }
  if (filters.dateTo) {
    params.set("dateTo", filters.dateTo);
  }
  if (filters.page) {
    params.set("page", String(filters.page));
  }
  if (filters.pageSize) {
    params.set("pageSize", String(filters.pageSize));
  }
  const qs = params.toString();
  return apiRequest<MarketHistoryList>(
    `/leagues/${leagueId}/mercato/storico${qs ? `?${qs}` : ""}`,
    { accessToken },
  );
}
