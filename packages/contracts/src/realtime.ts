/**
 * Eventi in tempo reale (SSE) — `GET /realtime/stream?leagueIds=a,b` (EP09-07).
 *
 * Auth Bearer come il resto dell'API. Ogni messaggio è una riga `data: {json}`.
 * Gli eventi sono segnali: portano solo tipo e id, il client ricarica i dati con
 * le sue chiamate. Il flusso si chiude da solo ogni ~10 minuti (il token scade):
 * il client si riconnette. 503 `realtime_unavailable` = nessun Redis, si resta
 * sul polling.
 */
export const REALTIME_STREAM_PATH = "/realtime/stream";

/** Nuova notifica per l'utente collegato (canale personale). */
export interface NotificationCreatedEvent {
  type: "notification.created";
  notificationId: string;
  category: "sistema" | "formazione" | "mercato" | "risultati";
}

/**
 * Qualcosa è cambiato nel mercato di una lega di cui l'utente è membro.
 * `trades` = proposte di scambio; `auction_live` = asta live (con `sessionId`);
 * `market` = tutto il resto (buste chiuse, rilasci, svincolati…).
 */
export interface MarketUpdatedEvent {
  type: "market.updated";
  kind: "trades" | "auction_live" | "market";
  leagueId: string;
  sessionId?: string;
}

export type RealtimeEvent = NotificationCreatedEvent | MarketUpdatedEvent;
