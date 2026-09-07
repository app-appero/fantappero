import type {
  ConfigureLiveAuctionSessionRequest,
  CreateLiveAuctionSessionRequest,
  LiveAuctionSession,
  LiveLot,
  LiveLotList,
  LiveLotState,
  NominateLotRequest,
  PlaceRaiseRequest,
  ResolveSwapRequest,
} from "@fantappero/contracts";
import { apiRequest } from "./client";

// -- Asta a rilanci (EP08-09) --------------------------------------------------

export function createLiveAuctionSession(
  accessToken: string,
  leagueId: string,
  body: CreateLiveAuctionSessionRequest,
): Promise<LiveAuctionSession> {
  return apiRequest<LiveAuctionSession>(`/leagues/${leagueId}/mercato/asta-live/sessioni`, {
    accessToken,
    method: "POST",
    body,
  });
}

export function configureLiveAuctionSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  body: ConfigureLiveAuctionSessionRequest,
): Promise<LiveAuctionSession> {
  return apiRequest<LiveAuctionSession>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/configurazione`,
    { accessToken, method: "PUT", body },
  );
}

export function fetchLiveAuctionSessions(
  accessToken: string,
  leagueId: string,
): Promise<LiveAuctionSession[]> {
  return apiRequest<LiveAuctionSession[]>(`/leagues/${leagueId}/mercato/asta-live/sessioni`, {
    accessToken,
  });
}

export function fetchLiveAuctionSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<LiveAuctionSession> {
  return apiRequest<LiveAuctionSession>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}`,
    { accessToken },
  );
}

export function startLiveAuctionSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<LiveAuctionSession> {
  return apiRequest<LiveAuctionSession>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/avvia`,
    { accessToken, method: "POST" },
  );
}

export function endLiveAuctionSession(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<LiveAuctionSession> {
  return apiRequest<LiveAuctionSession>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/termina`,
    { accessToken, method: "POST" },
  );
}

export function nominateLiveAuctionLot(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  body: NominateLotRequest,
): Promise<LiveLot> {
  return apiRequest<LiveLot>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/lotti/nomina`,
    { accessToken, method: "POST", body },
  );
}

export function placeLiveAuctionRaise(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  lotId: string,
  body: PlaceRaiseRequest,
): Promise<LiveLot> {
  return apiRequest<LiveLot>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/lotti/${lotId}/rilanci`,
    { accessToken, method: "PUT", body },
  );
}

export function forceSellLiveAuctionLot(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  lotId: string,
): Promise<LiveLot> {
  return apiRequest<LiveLot>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/lotti/${lotId}/aggiudica`,
    { accessToken, method: "POST" },
  );
}

export function passLiveAuctionLot(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  lotId: string,
): Promise<LiveLot> {
  return apiRequest<LiveLot>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/lotti/${lotId}/salta`,
    { accessToken, method: "POST" },
  );
}

export function cancelLiveAuctionLot(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  lotId: string,
): Promise<LiveLot> {
  return apiRequest<LiveLot>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/lotti/${lotId}/annulla`,
    { accessToken, method: "POST" },
  );
}

export function resolveLiveAuctionSwap(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  lotId: string,
  body: ResolveSwapRequest,
): Promise<LiveLot> {
  return apiRequest<LiveLot>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/lotti/${lotId}/scambia`,
    { accessToken, method: "POST", body },
  );
}

export function declineLiveAuctionSwap(
  accessToken: string,
  leagueId: string,
  sessionId: string,
  lotId: string,
): Promise<LiveLot> {
  return apiRequest<LiveLot>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/lotti/${lotId}/rinuncia-scambio`,
    { accessToken, method: "POST" },
  );
}

export function fetchLiveAuctionState(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<LiveLotState> {
  return apiRequest<LiveLotState>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/stato`,
    { accessToken },
  );
}

export function fetchLiveAuctionLots(
  accessToken: string,
  leagueId: string,
  sessionId: string,
): Promise<LiveLotList> {
  return apiRequest<LiveLotList>(
    `/leagues/${leagueId}/mercato/asta-live/sessioni/${sessionId}/lotti`,
    { accessToken },
  );
}
